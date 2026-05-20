# 手动触发操作面板 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将定时任务暴露为可手动触发的操作面板，支持 SSE 流式展示执行过程，具备扩展性。

**Architecture:** Agent 新增 `handle_scheduled_stream()` 方法；路由新增 `GET /api/actions` 和 `POST /api/actions/stream`；前端新增"操作"Tab，提取共享流式渲染函数。

**Tech Stack:** Python/FastAPI/SSE（后端），vanilla JS/CSS（前端），pytest/httpx（测试）

---

### Task 1: Agent — 提取 SCHEDULED_PROMPTS 常量并新增 send_email

**Files:**
- Modify: `src/core/agent.py:14-35`

- [ ] **Step 1: 在 agent.py 顶部新增模块级常量 SCHEDULED_PROMPTS**

```python
SCHEDULED_PROMPTS = {
    "periodic_check": "现在是定时检查。请分析用户的 GitHub 最近提交，搜索前沿方向，反思近期对话并准备学习周报。如果一切正常，最后发送邮件。",
    "reflect": "现在是自我反思时间。请审视近期的所有对话和分析结果，提炼经验，更新知识图谱，必要时创建 Skill。",
    "send_email": "请使用 send_email 工具立即发送所有待发邮件。合并待发队列中的内容，润色后发送。",
}
```

- [ ] **Step 2: 修改 `handle_scheduled` 方法，将内联 prompt_map 替换为引用 SCHEDULED_PROMPTS**

将 `handle_scheduled` 中第 63-66 行的 `prompt_map` 字典替换为：

```python
initial = SCHEDULED_PROMPTS.get(trigger, f"执行任务：{trigger}")
```

删除原来的 4 行 `prompt_map = {...}` 块。

- [ ] **Step 3: 验证 Agent 模块可导入且 handle_scheduled 仍工作**

Run: `python -c "from src.core.agent import Agent, SCHEDULED_PROMPTS; assert 'send_email' in SCHEDULED_PROMPTS; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/core/agent.py
git commit -m "refactor: 提取 SCHEDULED_PROMPTS 常量，新增 send_email 触发词

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Agent — 新增 handle_scheduled_stream 方法

**Files:**
- Modify: `src/core/agent.py:78-96`（在 `handle_scheduled` 之后插入新方法）

- [ ] **Step 1: 在 `handle_scheduled` 方法之后、`handle_message_stream` 之前插入新方法**

```python
    async def handle_scheduled_stream(self, trigger: str, model_id: str = ""):
        """流式版 handle_scheduled，返回 async generator，yield SSE 事件 dict。"""
        try:
            context = retrieve_relevant_context(trigger)

            initial = SCHEDULED_PROMPTS.get(trigger, f"执行任务：{trigger}")
            agent_logger.info("[SYSTEM] 流式触发: %s", trigger)
            self.short_term.add("system", initial)

            async for event in self._agent_loop_stream(
                trigger=trigger,
                initial_context=context,
                max_rounds=8,
                model_id=model_id,
            ):
                yield event
        except Exception as e:
            yield {"type": "error", "message": f"处理失败: {str(e)}"}
        finally:
            self._persist_and_clear()
            result = await commit_and_push()
            if result:
                agent_logger.info("[SYSTEM] Git: %s", result)
```

- [ ] **Step 2: 验证新方法可导入且不破坏已有代码**

Run: `python -c "from src.core.agent import Agent; a = Agent(); import inspect; assert inspect.isasyncgenfunction(a.handle_scheduled_stream); print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/core/agent.py
git commit -m "feat: Agent 新增 handle_scheduled_stream 流式触发方法

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: Routes — 新增 ACTIONS 常量和 GET /api/actions

**Files:**
- Modify: `src/web/routes.py:474-482`（在反射端点之后追加）

- [ ] **Step 1: 在 routes.py 的 import 区域之后添加 ACTIONS 常量**

在 `router = APIRouter()` 之后（第 9 行之后）添加：

```python
ACTIONS = [
    {
        "trigger": "periodic_check",
        "name": "周期检查",
        "description": "分析 GitHub 提交、搜索前沿方向、反思对话并准备学习周报",
        "icon": "🔄",
    },
    {
        "trigger": "reflect",
        "name": "自我反思",
        "description": "审视近期对话和分析结果，提炼经验，更新知识图谱",
        "icon": "🧠",
    },
    {
        "trigger": "send_email",
        "name": "发送邮件",
        "description": "合并待发队列中的内容，LLM 润色后发送学习周报",
        "icon": "✉️",
    },
]
```

- [ ] **Step 2: 在文件末尾添加 GET /api/actions 端点**

```python
@router.get("/api/actions")
async def list_actions():
    """返回可手动触发的操作列表。"""
    return {"actions": ACTIONS}
```

- [ ] **Step 3: 验证端点正确返回**

Run: `python -c "from src.web.routes import ACTIONS; assert len(ACTIONS) == 3; assert ACTIONS[0]['trigger'] == 'periodic_check'; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/web/routes.py
git commit -m "feat: 新增 ACTIONS 配置常量和 GET /api/actions 端点

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: Routes — 新增 POST /api/actions/stream

**Files:**
- Modify: `src/web/routes.py`（在 Task 3 的新增代码之后追加）

- [ ] **Step 1: 在 imports 中确认 ActionRequest 模型**

在文件顶部添加 `ActionRequest` Pydantic 模型（与已有 `ChatRequest` 并列，第 22 行附近）：

```python
class ActionRequest(BaseModel):
    trigger: str
```

- [ ] **Step 2: 在文件末尾添加 POST /api/actions/stream 端点**

```python
@router.post("/api/actions/stream")
async def actions_stream(req: ActionRequest):
    """流式执行操作 SSE 端点。"""
    valid_triggers = {a["trigger"] for a in ACTIONS}
    if req.trigger not in valid_triggers:
        return JSONResponse(
            {"error": f"未知操作: {req.trigger}"}, status_code=400
        )

    agent = get_agent()

    async def event_generator():
        async for event in agent.handle_scheduled_stream(req.trigger):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 3: 验证端点已注册**

Run: `python -c "from src.web.routes import router; paths = [r.path for r in router.routes]; assert '/api/actions/stream' in paths; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/web/routes.py
git commit -m "feat: 新增 POST /api/actions/stream SSE 流式操作端点

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: 后端 API 测试

**Files:**
- Create: `tests/test_actions.py`

- [ ] **Step 1: 编写测试文件**

```python
"""测试操作面板 API 端点。"""
import json
import pytest
from httpx import AsyncClient, ASGITransport
from src.web.app import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_actions_endpoint_returns_list(client):
    """验证 GET /api/actions 返回正确的操作列表。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert "actions" in data
        assert len(data["actions"]) == 3
        triggers = [a["trigger"] for a in data["actions"]]
        assert "periodic_check" in triggers
        assert "reflect" in triggers
        assert "send_email" in triggers
        # 验证每条记录包含必要字段
        for a in data["actions"]:
            assert "trigger" in a
            assert "name" in a
            assert "description" in a
            assert "icon" in a


@pytest.mark.asyncio
async def test_actions_stream_endpoint_registered():
    """验证 POST /api/actions/stream 路由已注册。"""
    from src.web.routes import router
    paths = [r.path for r in router.routes]
    assert "/api/actions/stream" in paths


@pytest.mark.asyncio
async def test_actions_stream_invalid_trigger(client):
    """验证无效 trigger 返回 400 错误。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/actions/stream",
            json={"trigger": "invalid_trigger"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data


@pytest.mark.asyncio
async def test_actions_stream_returns_sse(client):
    """验证有效 trigger 返回 SSE text/event-stream。"""
    async with client.stream(
        "POST", "/api/actions/stream",
        json={"trigger": "reflect"},
        timeout=60.0,
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        events = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                events.append(data)
            if len(events) >= 5:
                break

        assert len(events) > 0
        assert "type" in events[0]


@pytest.mark.asyncio
async def test_actions_list_matches_constant():
    """验证 API 返回的 actions 与后端 ACTIONS 常量一致。"""
    from src.web.routes import ACTIONS
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["actions"] == ACTIONS
```

- [ ] **Step 2: 运行快速验证的测试（不需要网络/LLM）**

Run: `pytest tests/test_actions.py::test_actions_endpoint_returns_list tests/test_actions.py::test_actions_stream_endpoint_registered tests/test_actions.py::test_actions_stream_invalid_trigger tests/test_actions.py::test_actions_list_matches_constant -v`

Expected: 4 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_actions.py
git commit -m "test: 新增操作面板 API 端点测试

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: 前端 — 提取共享流式渲染函数

**Files:**
- Modify: `src/web/templates/index.html`（JavaScript 区域，约 416-543 行）

- [ ] **Step 1: 在 `createStreamingMsg` 函数之前添加独立的 `createStreamingPanel` 函数**

在原来 `createStreamingMsg` 的定义处（第 432 行附近），将整个 `createStreamingMsg` 和 `handleSSEEvent` 块替换为：

```javascript
// ═══ 共享流式渲染（聊天 Tab 和操作 Tab 共用） ═══
function createStreamingPanel(container) {
    const wrapper = document.createElement('div');
    wrapper.className = 'msg assistant';
    container.appendChild(wrapper);

    let fullText = '';
    let toolDetails = null;
    let toolList = null;

    function scrollToBottom() {
        container.scrollTop = container.scrollHeight;
    }

    function appendText(chunk) {
        fullText += chunk;
        const html = renderMarkdown(fullText);
        wrapper.innerHTML = html;
        if (toolDetails) {
            wrapper.appendChild(toolDetails);
        }
        scrollToBottom();
    }

    function showToolStart(toolNames) {
        if (!toolDetails) {
            toolDetails = document.createElement('details');
            toolDetails.className = 'tool-steps';
            toolDetails.open = true;
            toolDetails.innerHTML = '<summary>正在调用工具...</summary>';
            toolList = document.createElement('div');
            toolList.className = 'tool-list';
            toolDetails.appendChild(toolList);
        }
        if (!toolDetails.parentNode) {
            wrapper.appendChild(toolDetails);
        }
    }

    function showToolStep(name, status) {
        if (!toolDetails) return;
        const icon = status === 'running' ? '⏳' :
                     status === 'done' ? '✅' : '❌';
        const existing = toolList.querySelector('.tool-step[data-tool="' + name + '"]');
        if (existing) {
            existing.className = 'tool-step ' + status;
            existing.textContent = icon + ' ' + name;
        } else {
            const step = document.createElement('div');
            step.className = 'tool-step ' + status;
            step.textContent = icon + ' ' + name;
            step.setAttribute('data-tool', name);
            toolList.appendChild(step);
        }
        if (status === 'done' || status === 'error') {
            const doneCount = toolList.querySelectorAll('.tool-step.done, .tool-step.error').length;
            const total = toolList.children.length;
            toolDetails.querySelector('summary').textContent =
                '⚙ 工具调用 (' + doneCount + '/' + total + ')';
        }
        scrollToBottom();
    }

    function hideTools() {
        if (toolDetails) {
            toolDetails.open = false;
        }
    }

    function finalize(errorText) {
        if (errorText) {
            wrapper.innerHTML = renderMarkdown(errorText);
        } else if (fullText) {
            wrapper.innerHTML = renderMarkdown(fullText);
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

// ═══ 聊天 Tab 流式 ═══
function createStreamingMsg() {
    return createStreamingPanel(chatMessages);
}
```

关键变化：`createStreamingPanel` 接受 `container` 参数，不再是硬编码 `chatMessages`；`createStreamingMsg` 变成一行委托调用。

- [ ] **Step 2: 验证页面 HTML 结构无语法错误**

Run: `python -c "with open('src/web/templates/index.html', 'r', encoding='utf-8') as f: content = f.read(); assert 'createStreamingPanel' in content; assert 'function createStreamingMsg' in content; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/web/templates/index.html
git commit -m "refactor: 提取 createStreamingPanel 为独立函数，操作 Tab 复用

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: 前端 — 新增操作 Tab HTML 结构 + CSS

**Files:**
- Modify: `src/web/templates/index.html`（侧边栏 + Tab 面板区域）
- Modify: `src/web/static/style.css`

- [ ] **Step 1: 在侧边栏添加"操作"按钮**

在 Skills 按钮之后（第 36 行 `<button ... data-tab="skills">` 之后）添加：

```html
            <button class="tab-btn" data-tab="actions"><span class="icon">&#9889;</span>操作</button>
```

- [ ] **Step 2: 在 Skills 面板之后添加操作 Tab 面板 HTML**

在第 114 行 `</div>`（Skills tab-panel 结束）之后、`</main>` 之前添加：

```html

            <!-- 操作 Tab -->
            <div class="tab-panel" id="panel-actions">
                <div id="action-cards" class="action-cards">
                    <!-- 动态从 /api/actions 加载 -->
                </div>
                <div id="action-stream" class="action-stream" style="display:none;">
                </div>
            </div>
```

- [ ] **Step 3: 更新 `switchTab` 函数中的标签映射**

修改第 246-248 行的 `switchTab` 函数中的映射对象：

将：
```javascript
    $('#current-tab-label').textContent = '— ' + ({
        chat:'聊天', reports:'报告', emails:'邮件', memories:'记忆', graph:'图谱', skills:'Skills'
    })[name] || '';
```

改为：
```javascript
    $('#current-tab-label').textContent = '— ' + ({
        chat:'聊天', reports:'报告', emails:'邮件', memories:'记忆', graph:'图谱', skills:'Skills', actions:'操作'
    })[name] || '';
```

- [ ] **Step 4: 更新懒加载逻辑，增加 actions Tab**

修改第 249-255 行的懒加载 if 块，在末尾添加：

```javascript
    if (name === 'actions' && !STATE.actionsLoaded) loadActions();
```

- [ ] **Step 5: 在 STATE 对象中增加 actionsLoaded 字段**

修改第 157-163 行的 STATE 对象：

在末尾添加：
```javascript
    actionsLoaded: false,
```

- [ ] **Step 6: 在 CSS 文件末尾添加操作面板样式**

在 `src/web/static/style.css` 末尾追加：

```css
/* ═══ 20. 操作面板 ═══ */
.action-cards {
    display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px;
}
.action-card {
    flex: 1; min-width: 200px; max-width: 280px;
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 24px 20px; text-align: center;
    transition: border-color 0.15s, box-shadow 0.15s, opacity 0.15s;
}
.action-card:hover { border-color: #6366f1; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
.action-card.running { opacity: 0.45; pointer-events: none; }
.action-card .action-icon { font-size: 36px; margin-bottom: 10px; }
.action-card .action-name { font-size: 15px; font-weight: 600; color: #1e293b; margin-bottom: 6px; }
.action-card .action-desc {
    font-size: 12px; color: #94a3b8; margin-bottom: 16px; line-height: 1.5;
}
.action-card .action-trigger {
    padding: 8px 24px; border: none; border-radius: 20px;
    background: #6366f1; color: #fff; cursor: pointer;
    font-weight: 600; font-size: 13px; transition: background 0.15s;
    font-family: inherit;
}
.action-card .action-trigger:hover { background: #4f46e5; }

.action-stream {
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 16px 20px; min-height: 200px; max-height: 500px; overflow-y: auto;
}
```

- [ ] **Step 7: Commit**

```bash
git add src/web/templates/index.html src/web/static/style.css
git commit -m "feat: 新增操作 Tab HTML 结构和 CSS 样式

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: 前端 — 操作 Tab JavaScript 交互逻辑

**Files:**
- Modify: `src/web/templates/index.html`（JavaScript 区域，Skills Tab 逻辑之后）

- [ ] **Step 1: 在 Skills Tab JS 代码块之后添加操作 Tab 逻辑**

在 `// ═══ Skills Tab ═══` 代码块的末尾（第 941 行 `renderSkillList();` 之后）添加：

```javascript

// ═══ 操作 Tab ═══
async function loadActions() {
    try {
        const data = await api('/api/actions');
        if (data && data.actions) {
            renderActionCards(data.actions);
            STATE.actionsLoaded = true;
        }
    } catch (e) {
        // api() 已处理 toast 提示
    }
}

function renderActionCards(actions) {
    const container = $('#action-cards');
    if (!container) return;
    container.innerHTML = '';

    actions.forEach(action => {
        const card = document.createElement('div');
        card.className = 'action-card';
        card.innerHTML = `
            <div class="action-icon">${action.icon}</div>
            <div class="action-name">${escapeHtml(action.name)}</div>
            <div class="action-desc">${escapeHtml(action.description)}</div>
            <button class="action-trigger" data-trigger="${action.trigger}">执行</button>
        `;
        container.appendChild(card);
    });

    container.querySelectorAll('.action-trigger').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            executeAction(btn.dataset.trigger);
        });
    });
}

async function executeAction(trigger) {
    // 禁用全部卡片
    const cards = document.querySelectorAll('.action-card');
    cards.forEach(c => c.classList.add('running'));

    // 显示流式面板
    const streamPanel = $('#action-stream');
    streamPanel.style.display = 'block';
    streamPanel.innerHTML = '';
    const streamCtrl = createStreamingPanel(streamPanel);

    try {
        const resp = await fetch('/api/actions/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trigger: trigger }),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || 'HTTP ' + resp.status);
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const event = JSON.parse(line.slice(6));
                        handleSSEEvent(event, streamCtrl);
                    } catch (e) {
                        // 忽略 JSON 解析错误
                    }
                }
            }
        }
    } catch (e) {
        streamCtrl.finalize('请求失败: ' + escapeHtml(e.message));
    }

    cards.forEach(c => c.classList.remove('running'));
}
```

- [ ] **Step 2: 在 STATE 对象中添加 actions 字段**

在 STATE 对象的 `actionsLoaded: false,` 之前或之后确保有 actions 相关状态（已在 Task 7 Step 5 添加了 `actionsLoaded`）。

- [ ] **Step 3: 验证 HTML 无语法错误**

Run: `python -c "with open('src/web/templates/index.html', 'r', encoding='utf-8') as f: content = f.read(); assert 'function loadActions' in content; assert 'function executeAction' in content; assert 'function renderActionCards' in content; print('OK')"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/web/templates/index.html
git commit -m "feat: 实现操作 Tab 卡片加载和 SSE 流式执行交互

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 9: 集成验证

**Files:**
- 无新建文件

- [ ] **Step 1: 运行全部后端测试**

Run: `pytest tests/ -v --timeout=120`

Expected: 所有测试通过（流式 SSE 测试可能需要网络/LLM，允许跳过）

- [ ] **Step 2: 启动开发服务器验证无导入错误**

Run: `python -c "from src.web.app import app; from src.core.agent import Agent; from src.web.routes import ACTIONS; print('All imports OK')"`

Expected: `All imports OK`

- [ ] **Step 3: 验证前端页面加载无 JS 语法错误（手动检查）**

启动 `python run.py`，打开浏览器，切换到"操作"Tab，确认：
- 3 张操作卡片正确渲染
- 点击"执行"后流式面板展开
- 工具调用步骤实时显示
- 完成后卡片恢复正常

- [ ] **Step 4: Commit（如有 lint 修复等微调）**

```bash
git add -A
git commit -m "chore: 集成验证，微调修复

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
