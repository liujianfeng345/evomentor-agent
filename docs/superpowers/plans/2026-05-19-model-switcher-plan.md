# 模型切换功能 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在聊天输入框左侧添加模型切换胶囊按钮，支持多个大模型选择和切换

**Architecture:** 后端 config.py 定义模型注册表 AVAILABLE_MODELS，LLMClient 根据 model_id 动态选择 API client；前端加载模型列表、localStorage 持久化偏好、通过 ChatRequest.model 字段传递选择

**Tech Stack:** FastAPI、OpenAI SDK、localStorage、原生 JavaScript

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/core/config.py` | 修改 | 新增 AVAILABLE_MODELS + DEFAULT_MODEL |
| `src/core/llm.py` | 修改 | 动态客户端 _get_client()，chat/chat_stream 加 model_id |
| `src/core/agent.py` | 修改 | 所有 handler 加 model_id 透传 |
| `src/web/routes.py` | 修改 | ChatRequest 加 model，新增 /api/models |
| `src/web/templates/index.html` | 修改 | 模型选择器 UI + JS 逻辑 |

---

### Task 1: config.py — 模型注册表

**Files:**
- Modify: `src/core/config.py:37`（Config 类末尾）

- [ ] **Step 1: 添加模型注册表和默认模型**

在 `Config` 类中，`LLM_MAX_RETRIES` 之后添加：

```python
    # 模型注册表
    AVAILABLE_MODELS: list[dict] = [
        {
            "id": "deepseek-v4-flash",
            "name": "DeepSeek v4-flash",
            "provider": "deepseek",
            "model": os.getenv("DEEPSEEK_V4_FLASH_MODEL", "deepseek-chat"),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
            "icon": "⚡",
            "description": "快速响应，适合日常对话",
        },
        {
            "id": "deepseek-v4-pro",
            "name": "DeepSeek v4-pro",
            "provider": "deepseek",
            "model": os.getenv("DEEPSEEK_V4_PRO_MODEL", "deepseek-reasoner"),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
            "icon": "🧠",
            "description": "深度推理，适合复杂问题",
        },
    ]

    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "deepseek-v4-flash")
```

- [ ] **Step 2: 验证**

Run: `python -c "from src.core.config import config; print(len(config.AVAILABLE_MODELS), config.DEFAULT_MODEL)"`
Expected: `2 deepseek-v4-flash`

- [ ] **Step 3: Commit**

```bash
git add src/core/config.py
git commit -m "feat: config 新增模型注册表 AVAILABLE_MODELS"
```

---

### Task 2: llm.py — 动态客户端选择

**Files:**
- Modify: `src/core/llm.py`（__init__、chat、chat_stream）

- [ ] **Step 1: 重构 __init__**

将第 9-14 行的 `__init__` 替换为：

```python
    def __init__(self) -> None:
        self.models = {m["id"]: m for m in config.AVAILABLE_MODELS}
        self.default_model = config.DEFAULT_MODEL

    def _get_client(self, model_id: str):
        """根据模型 ID 获取对应的 OpenAI 客户端和底层模型名。"""
        model_id = model_id or self.default_model
        m = self.models.get(model_id)
        if not m:
            m = self.models[self.default_model]
        client = OpenAI(api_key=m["api_key"], base_url=m["base_url"])
        return client, m["model"]
```

- [ ] **Step 2: 修改 `chat()` 签名和内部调用**

将 `chat()` 的签名从：
```python
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> dict:
```

改为：
```python
    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        model_id: str = "",
    ) -> dict:
```

在方法体开头（`last_error` 之前）添加：
```python
        client, model_name = self._get_client(model_id)
```

将 `kwargs["model"] = self.model` 改为：
```python
                    "model": model_name,
```

- [ ] **Step 3: 修改 `chat_stream()` 签名和内部调用**

将 `chat_stream()` 签名从：
```python
    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ):
```

改为：
```python
    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        model_id: str = "",
    ):
```

在 kwargs 构建之前添加：
```python
        client, model_name = self._get_client(model_id)
```

将 `kwargs["model"] = self.model` 改为：
```python
            "model": model_name,
```

将所有 `self.client.chat.completions.create` 改为 `client.chat.completions.create`（共 1 处）。

- [ ] **Step 4: 验证**

Run: `python -c "from src.core.llm import llm; print(llm.default_model); c, m = llm._get_client('deepseek-v4-flash'); print(m)"`
Expected: `deepseek-v4-flash` 然后 `deepseek-chat`

- [ ] **Step 5: Commit**

```bash
git add src/core/llm.py
git commit -m "feat: LLMClient 支持动态模型切换 _get_client()"
```

---

### Task 3: agent.py — model_id 透传

**Files:**
- Modify: `src/core/agent.py`（handle_message、handle_message_stream、_agent_loop、_agent_loop_stream）

- [ ] **Step 1: 修改 `handle_message()` 签名**

将第 35 行的：
```python
    async def handle_message(self, user_message: str) -> str:
```

改为：
```python
    async def handle_message(self, user_message: str, model_id: str = "") -> str:
```

将第 42-46 行的 `_agent_loop` 调用增加 `model_id` 参数：
```python
        return await self._agent_loop(
            trigger="user_message",
            initial_context=context,
            max_rounds=5,
            model_id=model_id,
        )
```

- [ ] **Step 2: 修改 `_agent_loop()` 签名**

将第 83 行的：
```python
    async def _agent_loop(self, trigger: str, initial_context: str, max_rounds: int) -> str:
```

改为：
```python
    async def _agent_loop(self, trigger: str, initial_context: str, max_rounds: int, model_id: str = "") -> str:
```

将第 96 行的 `llm.chat(messages, tools=self.tools.get_schemas())` 改为：
```python
            response = llm.chat(messages, tools=self.tools.get_schemas(), model_id=model_id)
```

- [ ] **Step 3: 修改 `handle_message_stream()` 签名**

将第 66 行的：
```python
    async def handle_message_stream(self, user_message: str):
```

改为：
```python
    async def handle_message_stream(self, user_message: str, model_id: str = ""):
```

将第 72-76 行的 `_agent_loop_stream` 调用增加 `model_id`：
```python
            async for event in self._agent_loop_stream(
                trigger="user_message",
                initial_context=context,
                max_rounds=5,
                model_id=model_id,
            ):
```

- [ ] **Step 4: 修改 `_agent_loop_stream()` 签名**

将第 168 行的：
```python
    async def _agent_loop_stream(self, trigger: str, initial_context: str, max_rounds: int):
```

改为：
```python
    async def _agent_loop_stream(self, trigger: str, initial_context: str, max_rounds: int, model_id: str = ""):
```

将第 183 行的 `llm.chat_stream(messages, tools=self.tools.get_schemas())` 改为：
```python
            for chunk in llm.chat_stream(messages, tools=self.tools.get_schemas(), model_id=model_id):
```

- [ ] **Step 5: 验证**

Run: `python -c "from src.core.agent import Agent; a = Agent(); import inspect; sig = str(inspect.signature(a.handle_message)); print('model_id' in sig)"`
Expected: `True`

- [ ] **Step 6: Commit**

```bash
git add src/core/agent.py
git commit -m "feat: Agent 全部 handler 支持 model_id 透传"
```

---

### Task 4: routes.py — 模型列表 API + ChatRequest 扩展

**Files:**
- Modify: `src/web/routes.py`（ChatRequest、/api/chat、/api/chat/stream、新增 /api/models）

- [ ] **Step 1: 修改 ChatRequest**

将第 22-23 行的 ChatRequest 改为：

```python
class ChatRequest(BaseModel):
    message: str
    model: str = ""  # 模型 ID，空则用默认
```

- [ ] **Step 2: 修改 /api/chat 端点**

将第 37 行的：
```python
    reply = await agent.handle_message(req.message)
```

改为：
```python
    reply = await agent.handle_message(req.message, model_id=req.model)
```

- [ ] **Step 3: 修改 /api/chat/stream 端点**

将第 52 行的：
```python
        async for event in agent.handle_message_stream(req.message):
```

改为：
```python
        async for event in agent.handle_message_stream(req.message, model_id=req.model):
```

- [ ] **Step 4: 新增 /api/models 端点**

在 `/api/health` 端点之后添加：

```python
@router.get("/api/models")
async def list_models():
    """返回可用模型列表（不含敏感信息如 API key）。"""
    from src.core.config import config
    return {
        "models": [
            {
                "id": m["id"],
                "name": m["name"],
                "provider": m["provider"],
                "icon": m.get("icon", ""),
                "description": m.get("description", ""),
            }
            for m in config.AVAILABLE_MODELS
        ],
        "default": config.DEFAULT_MODEL,
    }
```

- [ ] **Step 5: 验证端点注册**

Run: `python -c "from src.web.routes import router; paths = [r.path for r in router.routes]; print('/api/models' in paths)"`
Expected: `True`

- [ ] **Step 6: Commit**

```bash
git add src/web/routes.py
git commit -m "feat: ChatRequest 加 model 字段 + /api/models 端点"
```

---

### Task 5: index.html — 模型选择器 UI

**Files:**
- Modify: `src/web/templates/index.html`（输入区 DOM + JS 逻辑 + CSS）

- [ ] **Step 1: 修改输入区 DOM**

将当前第 43-46 行的：
```html
                <div id="input-area">
                    <textarea id="message" rows="2" placeholder="输入你的问题... (Enter 发送, Shift+Enter 换行)"></textarea>
                    <button id="send" onclick="sendMessage()">发送</button>
                </div>
```

替换为：
```html
                <div id="input-area">
                    <div id="model-selector" class="model-capsule" onclick="toggleModelMenu()">
                        <span id="current-model-icon">⚡</span>
                        <span id="current-model-name">加载中...</span>
                        <span class="model-arrow">▾</span>
                    </div>
                    <div id="model-menu" class="model-menu" style="display:none;"></div>
                    <textarea id="message" rows="2" placeholder="输入你的问题... (Enter 发送, Shift+Enter 换行)"></textarea>
                    <button id="send" onclick="sendMessage()">发送</button>
                </div>
```

- [ ] **Step 2: 添加 CSS**

在现有 `#input-area { flex-shrink: 0; display: flex; gap: 10px; align-items: center; }` 样式附近（确认此规则仍存在，style.css 中已有），在 style.css 末尾追加：

```css
/* ═══ 19. Model Switcher ═══ */
#input-area { position: relative; }
.model-capsule {
    display: flex; align-items: center; gap: 6px;
    padding: 8px 14px; border-radius: 24px;
    border: 1px solid #e2e8f0; background: #f8fafc;
    cursor: pointer; white-space: nowrap; font-size: 13px;
    color: #334155; user-select: none;
    transition: border-color 0.15s, background 0.15s;
    flex-shrink: 0;
}
.model-capsule:hover { border-color: #6366f1; background: #eef2ff; }
.model-capsule.open { border-color: #6366f1; background: #eef2ff; color: #6366f1; }

.model-arrow { font-size: 10px; color: #94a3b8; transition: transform 0.2s; }
.model-capsule.open .model-arrow { transform: rotate(180deg); }

.model-menu {
    position: absolute; bottom: 56px; left: 0;
    background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.08); min-width: 230px;
    padding: 6px; z-index: 100;
}
.model-menu .model-option {
    display: flex; align-items: center; gap: 8px;
    padding: 10px 12px; border-radius: 8px; cursor: pointer;
    transition: background 0.1s;
}
.model-menu .model-option:hover { background: #f1f5f9; }
.model-menu .model-option.selected { background: #eef2ff; }
.model-menu .model-option .model-icon { font-size: 16px; width: 28px; text-align: center; flex-shrink: 0; }
.model-menu .model-option .model-info { flex: 1; }
.model-menu .model-option .model-name { font-size: 13px; font-weight: 600; color: #1e293b; }
.model-menu .model-option .model-desc { font-size: 11px; color: #94a3b8; margin-top: 1px; }
.model-menu .model-option .model-check { color: #6366f1; font-size: 14px; }
.model-menu .model-provider {
    padding: 6px 12px 2px; font-size: 11px; color: #94a3b8;
    border-top: 1px solid #e2e8f0; margin-top: 4px;
}
```

- [ ] **Step 3: 添加 JS 逻辑**

在 `<script>` 中，`// ═══ 聊天 Tab ═══` 注释块之前，添加完整的模型选择器 JS：

```javascript
// ═══ 模型选择器 ═══
let availableModels = [];
let currentModel = '';

async function initModelSelector() {
    try {
        const data = await api('/api/models');
        if (!data || !data.models || !data.models.length) return;
        availableModels = data.models;
        currentModel = localStorage.getItem('evomentor-model') || data.default;
        // 验证保存的模型是否仍可用
        if (!availableModels.find(m => m.id === currentModel)) {
            currentModel = data.default;
        }
        renderModelSelector();
    } catch (e) {
        // 模型列表加载失败，隐藏选择器
        document.getElementById('model-selector').style.display = 'none';
    }
}

function renderModelSelector() {
    const model = availableModels.find(m => m.id === currentModel);
    if (!model) return;
    document.getElementById('current-model-icon').textContent = model.icon;
    document.getElementById('current-model-name').textContent = model.name;
}

function toggleModelMenu() {
    const menu = document.getElementById('model-menu');
    const capsule = document.getElementById('model-selector');
    if (!menu || !capsule || availableModels.length === 0) return;
    if (menu.style.display === 'none' || !menu.style.display) {
        renderModelMenu();
        menu.style.display = 'block';
        capsule.classList.add('open');
    } else {
        menu.style.display = 'none';
        capsule.classList.remove('open');
    }
}

function selectModel(modelId) {
    currentModel = modelId;
    localStorage.setItem('evomentor-model', modelId);
    renderModelSelector();
    document.getElementById('model-menu').style.display = 'none';
    document.getElementById('model-selector').classList.remove('open');
}

function renderModelMenu() {
    const menu = document.getElementById('model-menu');
    const providers = [...new Set(availableModels.map(m => m.provider))];
    menu.innerHTML = '';
    providers.forEach((provider) => {
        availableModels.filter(m => m.provider === provider).forEach(model => {
            const selected = model.id === currentModel;
            const div = document.createElement('div');
            div.className = 'model-option' + (selected ? ' selected' : '');
            div.innerHTML = `
                <span class="model-icon">${model.icon}</span>
                <div class="model-info">
                    <div class="model-name">${model.name}</div>
                    <div class="model-desc">${model.description}</div>
                </div>
                ${selected ? '<span class="model-check">✓</span>' : ''}
            `;
            div.addEventListener('click', (e) => { e.stopPropagation(); selectModel(model.id); });
            menu.appendChild(div);
        });
    });
    const model = availableModels.find(m => m.id === currentModel);
    if (model) {
        menu.innerHTML += `<div class="model-provider">${model.provider} 提供</div>`;
    }
}

// 页面初始化时加载模型列表
initModelSelector();

// 全局点击事件：点击模型菜单外部关闭
document.addEventListener('click', (e) => {
    const menu = document.getElementById('model-menu');
    const capsule = document.getElementById('model-selector');
    if (menu && capsule && menu.style.display === 'block') {
        if (!capsule.contains(e.target) && !menu.contains(e.target)) {
            menu.style.display = 'none';
            capsule.classList.remove('open');
        }
    }
});
```

- [ ] **Step 4: 修改 sendMessage() 携带 model 参数**

将 `sendMessage()` 中 fetch 的 body 从：
```javascript
body: JSON.stringify({ message: text }),
```

改为：
```javascript
body: JSON.stringify({ message: text, model: currentModel }),
```

（共 1 处修改）

- [ ] **Step 5: 验证 HTML 结构**

```bash
python -c "
with open('src/web/templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()
assert 'model-selector' in html
assert 'initModelSelector()' in html
assert 'currentModel' in html
print('OK: model selector integrated')
"
```
Expected: `OK: model selector integrated`

- [ ] **Step 6: Commit**

```bash
git add src/web/templates/index.html src/web/static/style.css
git commit -m "feat: 前端模型选择器胶囊按钮 + localStorage 持久化"
```

---

### Task 6: 集成测试

**Files:**
- Modify: `tests/test_streaming.py`

- [ ] **Step 1: 添加模型列表 API 测试和模型参数测试**

在 `tests/test_streaming.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_models_endpoint_returns_list(client):
    """验证 /api/models 返回模型列表。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "default" in data
        assert len(data["models"]) >= 1
        for m in data["models"]:
            assert "id" in m
            assert "name" in m
            assert "provider" in m
            assert "icon" in m
            # 确认不泄露敏感信息
            assert "api_key" not in m


@pytest.mark.asyncio
async def test_chat_stream_supports_model_param(client):
    """验证流式端点接受 model 参数。"""
    async with client.stream(
        "POST", "/api/chat/stream",
        json={"message": "你好", "model": "deepseek-v4-flash"},
        timeout=60.0,
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        # 读取第一个事件确认连接正常
        events = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
            if len(events) >= 2:
                break
        assert len(events) > 0


@pytest.mark.asyncio
async def test_chat_stream_invalid_model_falls_back(client):
    """验证无效 model ID 回退到默认模型。"""
    async with client.stream(
        "POST", "/api/chat/stream",
        json={"message": "你好", "model": "nonexistent-model"},
        timeout=60.0,
    ) as resp:
        # 应该正常响应（回退到默认模型），不会报错
        assert resp.status_code == 200
```

- [ ] **Step 2: 运行新增测试**

```bash
pytest tests/test_streaming.py::test_models_endpoint_returns_list tests/test_streaming.py::test_chat_stream_supports_model_param tests/test_streaming.py::test_chat_stream_invalid_model_falls_back -v
```
Expected: 3 PASSED

- [ ] **Step 3: 运行全部流式测试无回归**

```bash
pytest tests/test_streaming.py -v
```
Expected: 8 PASSED

- [ ] **Step 4: Commit**

```bash
git add tests/test_streaming.py
git commit -m "test: 添加模型列表和模型参数集成测试"
```

---

### Task 7: 启动服务器手动验证

- [ ] **Step 1: 启动开发服务器**

```bash
python run.py
```

- [ ] **Step 2: 浏览器验证清单**

打开 `http://localhost:8000`，验证：

1. 输入框左侧出现模型选择器胶囊，默认显示 "v4-flash"
2. `curl http://localhost:8000/api/models` 返回 2 个模型
3. 点击胶囊弹出下拉菜单，显示两个模型选项
4. 选择 v4-pro，胶囊更新显示
5. 刷新页面，模型选择保持（localStorage）
6. 发送消息，消息正常流式回复
7. 点击菜单外部，菜单关闭
8. 网络断开时点击胶囊无反应（不崩溃）

- [ ] **Step 3: 如有问题，修复并追加 commit**

---

## 变更文件汇总

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/core/config.py` | 修改 | +15 行，AVAILABLE_MODELS + DEFAULT_MODEL |
| `src/core/llm.py` | 修改 | __init__ 重构 + _get_client() + chat/chat_stream 加 model_id |
| `src/core/agent.py` | 修改 | 4 个方法加 model_id 参数透传 |
| `src/web/routes.py` | 修改 | ChatRequest 加 model 字段 + /api/models 端点 |
| `src/web/static/style.css` | 修改 | +35 行，模型选择器 CSS |
| `src/web/templates/index.html` | 修改 | DOM + JS 逻辑 |
| `tests/test_streaming.py` | 修改 | +3 测试 |
