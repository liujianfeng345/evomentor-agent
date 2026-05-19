# 聊天流式输出 & Markdown 渲染 — 设计文档

日期：2026-05-19

## 需求概述

为聊天界面中大模型回复添加两个能力：
1. **流式输出**：LLM 回复逐 chunk 实时显示，而非等待完整响应后一次性展示
2. **Markdown 渲染**：LLM 回复中的 Markdown 语法正确渲染为富文本（标题、代码块、表格等）

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 通信协议 | SSE（Server-Sent Events） | 单向推送场景，HTTP 原生支持，FastAPI/浏览器双端成熟 |
| Markdown 渲染 | marked.js + highlight.js | 完整 GFM 支持 + 代码语法高亮 |
| 工具调用可见性 | 折叠面板（details/summary） | 默认简洁，用户可展开查看调用步骤 |
| 流式方法 | 新增流式链路，保留原有非流式 | 不破坏现有功能，非聊天场景仍用非流式 |

## 架构

```
浏览器 (index.html)
  │ fetch('/api/chat/stream') → ReadableStream 消费 SSE
  │ 累积文本 → marked.parse() → innerHTML 渲染
  ▼
FastAPI StreamingResponse (text/event-stream)
  │ SSE 事件: {type: "text"|"tool_start"|"tool_step"|"tool_end"|"done", ...}
  ▼
Agent._agent_loop_stream()  [新增]
  │ async generator, yield SSE 事件 dict
  │ Tool calls 累积拼接, 执行后 yield 状态事件
  ▼
LLMClient.chat_stream()  [新增]
  │ OpenAI SDK stream=True, yield delta chunks
```

## 后端改动

### 1. `src/core/llm.py` — 新增 `chat_stream()`

```python
def chat_stream(self, messages, tools=None, temperature=0.7):
    """流式聊天，yield 每个 delta chunk。"""
    kwargs = {"model": self.model, "messages": messages,
              "temperature": temperature, "stream": True}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    response = self.client.chat.completions.create(**kwargs)
    for chunk in response:
        delta = chunk.choices[0].delta
        yield {
            "content": delta.content or "",
            "role": delta.role or "",
            "tool_calls": delta.tool_calls or [],
            "finish_reason": chunk.choices[0].finish_reason or "",
        }
```

要点：
- `stream=True` 后 SDK 返回迭代器
- tool_calls 流式到达时需累积拼接（id/name 先到，arguments 分片后到）
- 保留原 `chat()` 方法不动

### 2. `src/core/agent.py` — 新增 `_agent_loop_stream()` + `handle_message_stream()`

```python
async def handle_message_stream(self, user_message: str):
    """流式版 handle_message，返回 async generator。"""
    context = retrieve_relevant_context(user_message)
    self.short_term.add("user", user_message)
    async for event in self._agent_loop_stream(
        trigger="user_message", initial_context=context, max_rounds=5
    ):
        yield event

async def _agent_loop_stream(self, trigger, initial_context, max_rounds):
    """流式版 Agent 循环，yield SSE 事件 dict。"""
    for _ in range(max_rounds):
        # 构建 messages（同现有逻辑）
        messages = [...]
        response_gen = llm.chat_stream(messages, tools=self.tools.get_schemas())

        content_buffer = ""
        tool_calls_buffer = {}

        for chunk in response_gen:
            if chunk["tool_calls"]:
                for tc in chunk["tool_calls"]:
                    idx = tc.index
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {
                            "id": tc.id or "",
                            "name": tc.function.name or "",
                            "arguments": ""
                        }
                    if tc.function.arguments:
                        tool_calls_buffer[idx]["arguments"] += tc.function.arguments
            elif chunk["content"]:
                content_buffer += chunk["content"]
                yield {"type": "text", "content": chunk["content"]}

        if tool_calls_buffer:
            yield {
                "type": "tool_start",
                "tools": [{"name": v["name"]} for v in tool_calls_buffer.values()]
            }
            for tc_data in tool_calls_buffer.values():
                yield {"type": "tool_step", "name": tc_data["name"], "status": "running"}
                tool = self.tools.get(tc_data["name"])
                if tool:
                    args = json.loads(tc_data["arguments"])
                    result = await tool.execute(**args)
                    # 写入 short_term
                yield {"type": "tool_step", "name": tc_data["name"], "status": "done"}
            yield {"type": "tool_end"}
            continue  # 继续下一轮循环

        if content_buffer:
            self.short_term.add("assistant", content_buffer)
        yield {"type": "done"}
        break

    # 持久化 + 清除短期记忆（同现有逻辑）
```

### 3. `src/web/routes.py` — 新增 `/api/chat/stream` 端点

```python
@router.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    agent = get_agent()
    async def event_generator():
        async for event in agent.handle_message_stream(req.message):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

## 前端改动

### 4. `src/web/templates/index.html`

#### 4.1 引入依赖

```html
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/highlight.js/styles/github-dark.min.css">
<script src="https://cdn.jsdelivr.net/npm/highlight.js/lib/core.min.js"></script>
```

#### 4.2 改造 `sendMessage()`

- 使用 `fetch()` + `ReadableStream` 消费 SSE 事件
- 按 SSE 协议解析 (`data: {...}\n\n`)
- 根据 `type` 分发处理：`text` → 累积文本并渲染 / `tool_step` → 更新折叠面板 / `done` → 完成

#### 4.3 `createStreamingMsg()` 组件

- 返回 `{ appendText, showToolStep, finalize }` 三个控制函数
- `appendText(chunk)`：累积文本 + `marked.parse()` 实时渲染 + `innerHTML` 更新
- `showToolStep(name, status)`：维护一个 `<details>` 折叠面板，展示工具调用进度
- `finalize(text)`：出错时显示错误信息

#### 4.4 CSS 调整

- **移除** `.msg` 的 `white-space: pre-wrap;`（会破坏 markdown 渲染的布局）
- 新增 `.msg.assistant h2/h3/h4/code/pre/table/th/td/blockquote/ul/ol/a` 样式
- 新增 `.tool-steps` 折叠面板样式（灰色小字，运行中黄/完成绿）

#### 4.5 configure marked

```javascript
marked.setOptions({ breaks: true, gfm: true });
// 配置 highlight.js
```

## SSE 事件协议

| type | payload | 说明 |
|------|---------|------|
| `text` | `{content: string}` | LLM 回复文本片段 |
| `tool_start` | `{tools: [{name}]}` | 开始调用工具（前端创建折叠区） |
| `tool_step` | `{name, status: "running"\|"done"}` | 单个工具状态变更 |
| `tool_end` | `{}` | 工具调用阶段结束 |
| `done` | `{}` | 流式传输结束 |

## 错误处理

- 网络断开：前端 `fetch` 抛出异常 → catch 中 `finalize('连接中断: ...')`
- LLM 调用失败：后端 `chat_stream()` 内部重试 3 次，仍失败则 yield `{"type": "error", "message": "..."}`
- JSON 解析失败：tool_calls arguments 累积后 `json.loads` 失败 → yield `{"type": "tool_step", "name": tc, "status": "error"}` 并跳过该工具

## 不变部分

- 非流式 `/api/chat` 端点保留不动
- 邮件、报告、记忆等 Tab 不受影响
- Agent 非流式方法 `handle_message()` / `handle_scheduled()` 保留不动

## 测试要点

1. 发送消息 → LLM 回复逐字出现（非一次性显示）
2. Markdown 标题/粗体/代码块/表格正确渲染
3. 代码块语法高亮生效
4. 工具调用时折叠面板出现，可展开查看步骤
5. 网络断开时显示错误信息而非卡死
6. 用户消息也享受 MD 渲染（代码片段等）
