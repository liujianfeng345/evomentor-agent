# 聊天流式输出 & Markdown 渲染 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 聊天界面 LLM 回复支持流式逐字输出和 Markdown 富文本渲染

**Architecture:** 后端新增流式链路（LLMClient.chat_stream → Agent._agent_loop_stream → SSE 端点），前端用 fetch ReadableStream 消费 SSE 事件，累积文本后用 marked.js + highlight.js 实时渲染。原有非流式链路完全保留不动。

**Tech Stack:** FastAPI StreamingResponse, OpenAI SDK stream=True, marked.js, highlight.js (github-dark 主题)

---

### Task 1: LLMClient 流式调用

**Files:**
- Modify: `src/core/llm.py`（末尾追加新方法）

- [ ] **Step 1: 添加 `chat_stream()` 方法**

在 `LLMClient` 类末尾（`llm = LLMClient()` 之前）添加：

```python
    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ):
        """流式聊天，yield 每个 delta chunk。
        
        tool_calls 在流式模式下分片到达，调用方需自行累积拼接。
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        last_error = None
        for attempt in range(config.LLM_MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(**kwargs)
                for chunk in response:
                    delta = chunk.choices[0].delta
                    yield {
                        "content": delta.content or "",
                        "role": delta.role or "",
                        "tool_calls": delta.tool_calls or [],
                        "finish_reason": chunk.choices[0].finish_reason or "",
                    }
                return  # 正常结束
            except Exception as e:
                last_error = e
                if attempt < config.LLM_MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM 流式调用失败（已重试 {config.LLM_MAX_RETRIES} 次）: {last_error}")
```

- [ ] **Step 2: 验证模块可导入**

Run: `python -c "from src.core.llm import llm; print(hasattr(llm, 'chat_stream'))"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add src/core/llm.py
git commit -m "feat: LLMClient 新增 chat_stream 流式方法

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Agent 流式循环

**Files:**
- Modify: `src/core/agent.py`（在 `_agent_loop` 方法后追加，在 `class Agent` 内部）

- [ ] **Step 1: 添加 `handle_message_stream()` 方法**

在 `handle_scheduled()` 方法之后、`_agent_loop()` 之前添加：

```python
    async def handle_message_stream(self, user_message: str):
        """流式版 handle_message，返回 async generator，yield SSE 事件 dict。"""
        context = retrieve_relevant_context(user_message)
        self.short_term.add("user", user_message)

        # 在线程池中运行同步生成器，避免阻塞事件循环
        async for event in self._agent_loop_stream(
            trigger="user_message",
            initial_context=context,
            max_rounds=5,
        ):
            yield event

        # 持久化 + 清除短期记忆
        self._persist_and_clear()
```

- [ ] **Step 2: 添加 `_persist_and_clear()` 辅助方法**

在 `_agent_loop()` 方法之后添加：

```python
    def _persist_and_clear(self):
        """持久化对话到长期存储，清除短期记忆。"""
        for msg in self.short_term.get_all():
            lts.save_conversation(
                role=msg.role, content=msg.content,
                tags=msg.tags, intent=msg.intent,
                session_id=self.session_id,
            )
        self.short_term.clear()
```

- [ ] **Step 3: 添加 `_agent_loop_stream()` 方法**

紧接着添加：

```python
    async def _agent_loop_stream(self, trigger: str, initial_context: str, max_rounds: int):
        """流式版 Agent 循环，yield SSE 事件 dict。"""
        context = initial_context

        for _ in range(max_rounds):
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": f"## 相关记忆\n{context}"},
            ]
            messages.extend(self.short_term.get_for_llm())

            tool_calls_buffer: dict[int, dict] = {}
            content_buffer = ""

            for chunk in llm.chat_stream(messages, tools=self.tools.get_schemas()):
                if chunk["tool_calls"]:
                    for tc in chunk["tool_calls"]:
                        idx = tc.index
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name or "",
                                "arguments": "",
                            }
                        if tc.function.arguments:
                            tool_calls_buffer[idx]["arguments"] += tc.function.arguments

                elif chunk["content"]:
                    content_buffer += chunk["content"]
                    yield {"type": "text", "content": chunk["content"]}

            # 如果没有 tool_calls，直接结束
            if not tool_calls_buffer:
                if content_buffer:
                    self.short_term.add("assistant", content_buffer)
                yield {"type": "done"}
                return

            # 有 tool_calls：通知前端、执行工具、继续循环
            tools_list = [{"name": v["name"]} for v in tool_calls_buffer.values()]
            yield {"type": "tool_start", "tools": tools_list}

            # 构建 assistant tool_calls 消息
            tool_calls_schema = [
                {
                    "id": v["id"],
                    "type": "function",
                    "function": {"name": v["name"], "arguments": v["arguments"]},
                }
                for v in tool_calls_buffer.values()
            ]
            self.short_term.add_assistant_tool_calls(
                content_buffer, tool_calls_schema
            )

            for tc_data in tool_calls_buffer.values():
                name = tc_data["name"]
                yield {"type": "tool_step", "name": name, "status": "running"}

                tool = self.tools.get(name)
                if tool:
                    try:
                        args = json.loads(tc_data["arguments"])
                        result = await tool.execute(**args)
                        self.short_term.add_tool_result(
                            name, result.content,
                            tool_call_id=tc_data["id"],
                        )
                        if result.metadata:
                            context += f"\n{name} 元数据: {result.metadata}"
                        yield {"type": "tool_step", "name": name, "status": "done"}
                    except (json.JSONDecodeError, Exception) as e:
                        self.short_term.add_tool_result(
                            name, f"执行失败: {e}",
                            tool_call_id=tc_data["id"],
                        )
                        yield {"type": "tool_step", "name": name, "status": "error"}
                else:
                    yield {"type": "tool_step", "name": name, "status": "error"}

            yield {"type": "tool_end"}

        # max_rounds 用尽
        yield {"type": "done"}
```

- [ ] **Step 4: 重构 `_agent_loop()` 复用 `_persist_and_clear()`**

将 `_agent_loop()` 末尾的持久化+清除逻辑替换为调用新方法。

找到 `_agent_loop()` 末尾这几行：

```python
        # 保存对话到长期存储
        for msg in self.short_term.get_all():
            lts.save_conversation(
                role=msg.role, content=msg.content,
                tags=msg.tags, intent=msg.intent,
                session_id=self.session_id,
            )

        # 清除短期记忆，避免下次调用时残留历史 tool_calls 导致 API 错误
        self.short_term.clear()

        return final_response
```

替换为：

```python
        self._persist_and_clear()
        return final_response
```

- [ ] **Step 5: 验证模块可导入**

Run: `python -c "from src.core.agent import Agent; a = Agent(); print(hasattr(a, 'handle_message_stream'))"`
Expected: `True`

- [ ] **Step 6: Commit**

```bash
git add src/core/agent.py
git commit -m "feat: Agent 新增流式循环 _agent_loop_stream

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: SSE 端点

**Files:**
- Modify: `src/web/routes.py:1-8`（顶部的 imports）+ `routes.py:33-37`（新增端点）

- [ ] **Step 1: 添加 imports**

在文件顶部 `from fastapi.responses import JSONResponse` 之后添加：

```python
from fastapi.responses import StreamingResponse
import json as json_module
```

实际只需修改 import 行，让 `json` 可用。查看现有导入：文件中已有 `import os`，但 `json` 在 routes.py 中尚未导入，而 agent.py 中有。在 routes.py 顶部添加：

```python
import json
```

并将 `from fastapi.responses import JSONResponse` 改为：

```python
from fastapi.responses import JSONResponse, StreamingResponse
```

- [ ] **Step 2: 添加 SSE 端点**

在 `/api/health` 端点（第 40-42 行）之后、`"""报告与记忆相关的 API 端点。"""` 之前添加：

```python
@router.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式聊天 SSE 端点。"""
    agent = get_agent()

    async def event_generator():
        async for event in agent.handle_message_stream(req.message):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲（如有反向代理）
        },
    )
```

- [ ] **Step 3: 验证端点注册**

Run: `python -c "from src.web.routes import router; print([r.path for r in router.routes])"`
Expected: 列表中包含 `/api/chat/stream`

- [ ] **Step 4: Commit**

```bash
git add src/web/routes.py
git commit -m "feat: 新增 SSE 流式聊天端点 /api/chat/stream

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 前端 — 依赖引入与 marked 配置

**Files:**
- Modify: `src/web/templates/index.html`（`<head>` 区域和 `<style>` 区域）

- [ ] **Step 1: 添加 CDN 依赖**

在 `<style>` 结束标签 `</style>` 之后、`</head>` 之前添加：

```html
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/highlight.js@11/styles/github-dark.min.css">
    <script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/core.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/languages/python.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/languages/javascript.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/languages/bash.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/languages/json.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/languages/sql.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/highlight.js@11/lib/languages/css.min.js"></script>
```

- [ ] **Step 2: 配置 marked + highlight.js**

在 `<script>` 标签开头（`// ═══ 全局状态 ═══` 之前）添加：

```javascript
// 配置 marked
marked.setOptions({
    breaks: true,
    gfm: true,
});

// 配置 highlight.js
hljs.configure({ languages: [] });
marked.setOptions({
    highlight: function (code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            try {
                return hljs.highlight(code, { language: lang }).value;
            } catch (e) { /* fall through */ }
        }
        try {
            return hljs.highlightAuto(code).value;
        } catch (e) {
            return code;
        }
    },
});
```

- [ ] **Step 3: 修改 `addChatMsg` 使其支持 HTML 渲染**

找到 `addChatMsg` 函数（第 394-401 行），将其替换为：

```javascript
function addChatMsg(role, content, isLoading = false) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    if (isLoading) {
        div.classList.add('loading');
        div.textContent = content;
    } else if (role === 'assistant') {
        div.innerHTML = marked.parse(content);
    } else if (role === 'user') {
        div.innerHTML = simpleMd(content);
    }
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}
```

- [ ] **Step 4: Commit**

```bash
git add src/web/templates/index.html
git commit -m "feat: 前端引入 marked.js + highlight.js，聊天消息支持 MD 渲染

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: 前端 — 流式接收与 SSE 事件处理

**Files:**
- Modify: `src/web/templates/index.html`（替换 `sendMessage` 函数，新增辅助函数）

- [ ] **Step 1: 替换 `sendMessage()` 函数**

找到第 372-392 行的 `sendMessage()` 函数，整体替换为：

```javascript
async function sendMessage() {
    const text = msgInput.value.trim();
    if (!text) return;
    addChatMsg('user', text);
    msgInput.value = '';
    sendBtn.disabled = true;

    const streamCtrl = createStreamingMsg();

    try {
        const resp = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || `HTTP ${resp.status}`);
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop() || '';  // 最后一个可能是不完整的行

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const event = JSON.parse(line.slice(6));
                        handleSSEEvent(event, streamCtrl);
                    } catch (e) {
                        // 忽略 JSON 解析错误（可能是跨 chunk 的不完整行）
                    }
                }
            }
        }
    } catch (e) {
        streamCtrl.finalize('请求失败: ' + escapeHtml(e.message));
    }
    sendBtn.disabled = false;
}
```

- [ ] **Step 2: 新增 `createStreamingMsg()` 函数**

在 `sendMessage` 函数之后添加：

```javascript
function createStreamingMsg() {
    const wrapper = document.createElement('div');
    wrapper.className = 'msg assistant';
    chatMessages.appendChild(wrapper);

    let fullText = '';
    let toolDetails = null;
    let toolList = null;

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function appendText(chunk) {
        fullText += chunk;
        // 工具折叠区之后的内容单独渲染
        const parts = fullText.split('\n');
        const html = marked.parse(fullText);
        wrapper.innerHTML = html;
        // 如果工具折叠区已存在，重新挂载到末尾
        if (toolDetails) {
            wrapper.appendChild(toolDetails);
        }
        scrollToBottom();
    }

    function showToolStart(toolNames) {
        if (!toolDetails) {
            toolDetails = document.createElement('details');
            toolDetails.className = 'tool-steps';
            toolDetails.open = true;  // 默认展开
            toolDetails.innerHTML = '<summary>正在调用工具...</summary>';
            toolList = document.createElement('div');
            toolList.className = 'tool-list';
            toolDetails.appendChild(toolList);
        }
        // 确保在 DOM 末尾
        if (!toolDetails.parentNode) {
            wrapper.appendChild(toolDetails);
        }
    }

    function showToolStep(name, status) {
        if (!toolDetails) return;
        const icon = status === 'running' ? '⏳' :
                     status === 'done' ? '✅' : '❌';
        const step = document.createElement('div');
        step.className = 'tool-step ' + status;
        step.textContent = icon + ' ' + name;
        toolList.appendChild(step);
        toolDetails.querySelector('summary').textContent =
            '⚙ 已调用 ' + toolList.children.length + ' 个工具';
        scrollToBottom();
    }

    function hideTools() {
        if (toolDetails) {
            toolDetails.open = false;
        }
    }

    function finalize(errorText) {
        if (errorText) {
            wrapper.innerHTML = marked.parse(errorText);
        } else if (fullText) {
            wrapper.innerHTML = marked.parse(fullText);
            if (toolDetails) {
                wrapper.appendChild(toolDetails);
                toolDetails.open = false;
            }
        } else if (!toolDetails) {
            wrapper.innerHTML = '<span style="color:#888;">(空回复)</span>';
        }
        scrollToBottom();
    }

    return { appendText, showToolStart, showToolStep, hideTools, finalize };
}
```

- [ ] **Step 3: 新增 `handleSSEEvent()` 函数**

紧接着添加：

```javascript
function handleSSEEvent(event, streamCtrl) {
    switch (event.type) {
        case 'text':
            streamCtrl.appendText(event.content);
            break;
        case 'tool_start':
            streamCtrl.showToolStart(
                (event.tools || []).map(t => t.name)
            );
            break;
        case 'tool_step':
            streamCtrl.showToolStep(event.name, event.status);
            break;
        case 'tool_end':
            streamCtrl.hideTools();
            break;
        case 'done':
            streamCtrl.finalize(null);
            break;
        case 'error':
            streamCtrl.finalize(event.message || '未知错误');
            break;
    }
}
```

- [ ] **Step 4: Commit**

```bash
git add src/web/templates/index.html
git commit -m "feat: 前端实现 SSE 流式接收与实时 Markdown 渲染

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: 前端 — CSS 样式调整

**Files:**
- Modify: `src/web/templates/index.html`（`<style>` 区域）

- [ ] **Step 1: 移除 `.msg` 的 `white-space: pre-wrap`**

找到第 126 行：

```css
.msg { max-width: 80%; padding: 10px 14px; border-radius: 10px; line-height: 1.6; white-space: pre-wrap; font-size: 14px; }
```

替换为：

```css
.msg { max-width: 80%; padding: 10px 14px; border-radius: 10px; line-height: 1.6; font-size: 14px; word-wrap: break-word; overflow-wrap: break-word; }
```

- [ ] **Step 2: 添加 Markdown 渲染样式**

在第 133 行 `.loading` 样式之后添加：

```css

        /* Markdown 渲染样式 */
        .msg.assistant h1, .msg.assistant h2, .msg.assistant h3, .msg.assistant h4 {
            margin: 12px 0 6px; color: #58a6ff; font-weight: 600;
        }
        .msg.assistant h1 { font-size: 18px; }
        .msg.assistant h2 { font-size: 16px; }
        .msg.assistant h3 { font-size: 15px; }
        .msg.assistant h4 { font-size: 14px; }
        .msg.assistant p { margin: 4px 0; }
        .msg.assistant code {
            background: #1a1a2e; padding: 2px 6px; border-radius: 3px;
            font-family: 'Consolas', 'Courier New', monospace; font-size: 13px;
        }
        .msg.assistant pre {
            background: #0d1117; border-radius: 8px; padding: 12px 14px;
            overflow-x: auto; margin: 8px 0; border: 1px solid #0f3460;
        }
        .msg.assistant pre code { background: none; padding: 0; font-size: 13px; }
        .msg.assistant table {
            border-collapse: collapse; margin: 8px 0; width: 100%;
        }
        .msg.assistant th, .msg.assistant td {
            border: 1px solid #0f3460; padding: 6px 12px; text-align: left;
        }
        .msg.assistant th { background: #0f3460; font-weight: 600; }
        .msg.assistant blockquote {
            border-left: 3px solid #e94560; padding: 4px 12px;
            color: #aaa; margin: 8px 0; background: rgba(233,69,96,0.05);
            border-radius: 0 6px 6px 0;
        }
        .msg.assistant ul, .msg.assistant ol { padding-left: 24px; margin: 4px 0; }
        .msg.assistant li { margin: 2px 0; }
        .msg.assistant a { color: #58a6ff; text-decoration: underline; }
        .msg.assistant a:hover { color: #79b8ff; }
        .msg.assistant img { max-width: 100%; border-radius: 6px; margin: 4px 0; }
        .msg.assistant hr { border: none; border-top: 1px solid #0f3460; margin: 12px 0; }

        /* 工具调用折叠面板 */
        .tool-steps {
            margin-top: 10px; font-size: 12px; color: #888;
            background: rgba(15,52,96,0.2); border-radius: 6px;
            padding: 8px 12px; border: 1px solid #0f3460;
        }
        .tool-steps summary {
            cursor: pointer; color: #aaa; font-weight: 600;
            user-select: none;
        }
        .tool-steps summary:hover { color: #e0e0e0; }
        .tool-steps .tool-list { margin-top: 6px; }
        .tool-steps .tool-step { padding: 2px 0; }
        .tool-steps .tool-step.running { color: #bf8700; }
        .tool-steps .tool-step.done { color: #238636; }
        .tool-steps .tool-step.error { color: #e94560; }
```

- [ ] **Step 3: 在浏览器中打开 `http://localhost:5000`，确认样式正常**

手动验证：
1. 打开聊天 Tab
2. 确认现有消息样式未被破坏
3. 确认新样式定义已生效

- [ ] **Step 4: Commit**

```bash
git add src/web/templates/index.html
git commit -m "style: 聊天消息 Markdown 渲染样式 + 工具调用折叠面板样式

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: 集成测试

**Files:**
- Create: `tests/test_streaming.py`

- [ ] **Step 1: 编写流式 API 端点测试**

```python
"""测试流式聊天端点和 Markdown 渲染。"""
import json
import pytest
from httpx import AsyncClient, ASGITransport
from src.web.app import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_chat_stream_endpoint_exists():
    """验证流式端点已注册。"""
    from src.web.routes import router
    paths = [r.path for r in router.routes]
    assert "/api/chat/stream" in paths


@pytest.mark.asyncio
async def test_chat_stream_returns_sse_events(client):
    """验证流式端点返回 SSE 格式的 text/event-stream。"""
    async with client.stream(
        "POST", "/api/chat/stream",
        json={"message": "你好"},
        timeout=60.0,
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        # 读取至少一个事件
        events = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                events.append(data)
            if len(events) >= 5:  # 最多读 5 个事件后停止
                break

        assert len(events) > 0
        # 验证事件结构
        assert "type" in events[0]


@pytest.mark.asyncio
async def test_non_streaming_chat_still_works(client):
    """验证原有非流式端点不受影响。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/chat",
            json={"message": "你好"},
            timeout=60.0,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_streaming.py -v`
Expected: 3 tests PASS

- [ ] **Step 3: 运行全部已有测试确认无回归**

Run: `pytest tests/ -v --ignore=tests/test_streaming.py`
Expected: 所有已有测试 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_streaming.py
git commit -m "test: 添加流式聊天端点集成测试

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: 启动服务器手动验证

- [ ] **Step 1: 启动开发服务器**

Run: `python run.py`

- [ ] **Step 2: 浏览器验证清单**

打开 `http://localhost:5000`，在聊天 Tab 中逐一验证：

1. 发送 "你好" → 回复逐字出现（非一次性）
2. 发送 "用 Markdown 表格列出 Python 和 JS 的区别" → 表格正确渲染
3. 发送 "写一段 Python 快速排序代码" → 代码块有语法高亮
4. 发送 "分析我的 GitHub" → 工具调用折叠面板出现，可展开查看步骤
5. 网络断开时（关闭服务器）→ 显示错误信息
6. 用户消息中的 Markdown（如代码片段）也能渲染

- [ ] **Step 3: 如有问题，修复并追加 commit**

---

## 变更文件汇总

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/core/llm.py` | 修改 | 新增 `chat_stream()` 方法 |
| `src/core/agent.py` | 修改 | 新增 `handle_message_stream()`、`_agent_loop_stream()`、`_persist_and_clear()` |
| `src/web/routes.py` | 修改 | 新增 `/api/chat/stream` SSE 端点，新增 import |
| `src/web/templates/index.html` | 修改 | CDN 依赖、marked 配置、sendMessage 改写、流式组件、CSS |
| `tests/test_streaming.py` | 新建 | 流式端点集成测试 |
