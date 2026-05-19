# 模型切换功能 — 设计文档

日期：2026-05-19

## 需求概述

在聊天输入框左侧添加模型切换按钮，允许用户选择不同的大模型进行对话。当前支持 DeepSeek v4-flash 和 v4-pro，架构上预留多提供商扩展能力。用户选择通过 localStorage 持久化。

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 按钮位置 | 输入框左侧胶囊按钮 | 紧凑不占空间，与输入框风格统一 |
| 模型配置 | 后端配置驱动，API 返回列表 | 加模型只需改配置，不改前端代码 |
| 用户偏好 | localStorage 持久化 | 刷新/重开保持上次选择 |
| 模型传递 | ChatRequest 增加 model 字段 | 兼容现有 API，不选时用默认值 |

## 架构

```
localStorage               前端                    后端
    │                      │                       │
    ├─ model preference     │  GET /api/models      │
    │                       ├──────────────────────►│ config.AVAILABLE_MODELS
    │                       │◄──────────────────────┤
    │                       │  模型列表              │
    │                       │                       │
    │                       │  POST /api/chat/stream│
    │                       │  {message, model}     │
    │                       ├──────────────────────►│ LLMClient._get_client(id)
    │                       │◄──────────────────────┤ 动态选择 API key + URL
    │                       │  SSE 流式回复          │
    │                       │                       │
    │◄── 更新 localStorage   │                       │
```

## 后端改动

### 1. `src/core/config.py` — 模型注册表

新增：

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

### 2. `src/core/llm.py` — 动态客户端

`__init__` 改为：

```python
def __init__(self) -> None:
    self.models = {m["id"]: m for m in config.AVAILABLE_MODELS}
    self.default_model = config.DEFAULT_MODEL

def _get_client(self, model_id: str):
    """根据模型 ID 获取对应的 OpenAI 客户端和底层模型名。"""
    m = self.models.get(model_id)
    if not m:
        m = self.models[self.default_model]
    client = OpenAI(api_key=m["api_key"], base_url=m["base_url"])
    return client, m["model"]
```

`chat()` 和 `chat_stream()` 增加 `model_id` 参数，使用 `_get_client(model_id)` 获取动态客户端。

### 3. `src/web/routes.py` — 新增 API + 修改请求

**新增模型列表 API：**

```python
@router.get("/api/models")
async def list_models():
    """返回可用模型列表（不含敏感信息）。"""
    return {
        "models": [
            {
                "id": m["id"], "name": m["name"],
                "provider": m["provider"], "icon": m.get("icon", ""),
                "description": m.get("description", ""),
            }
            for m in config.AVAILABLE_MODELS
        ],
        "default": config.DEFAULT_MODEL,
    }
```

**修改 ChatRequest：**

```python
class ChatRequest(BaseModel):
    message: str
    model: str = ""  # 模型 ID，空则用默认
```

`/api/chat` 和 `/api/chat/stream` 将 `req.model` 传递给 Agent → LLMClient。

### 4. `src/core/agent.py` — 传递模型参数

`handle_message()` 和 `handle_message_stream()` 增加 `model_id` 参数，透传给 `llm.chat()` / `llm.chat_stream()`。

## 前端改动

### 5. `src/web/templates/index.html`

#### 5.1 新增 API 调用

```javascript
// 获取可用模型列表
async function loadModels() {
    try {
        const data = await api('/api/models');
        return data;  // {models: [...], default: "..."}
    } catch (e) {
        return null;
    }
}

// 从 localStorage 读取偏好模型
function getPreferredModel(defaultModel) {
    const saved = localStorage.getItem('evomentor-model');
    return saved || defaultModel;
}

// 保存模型偏好
function setPreferredModel(modelId) {
    localStorage.setItem('evomentor-model', modelId);
}
```

#### 5.2 输入区 DOM 改动

在 `#input-area` 中，`#message` textarea 之前添加模型选择器：

```html
<div id="input-area">
    <div id="model-selector" class="model-capsule" onclick="toggleModelMenu()">
        <span id="current-model-icon">⚡</span>
        <span id="current-model-name">v4-flash</span>
        <span class="model-arrow">▾</span>
    </div>
    <div id="model-menu" class="model-menu" style="display:none;">
        <!-- 动态填充 -->
    </div>
    <textarea id="message" ...></textarea>
    <button id="send" ...>发送</button>
</div>
```

#### 5.3 CSS 新增

```css
/* 模型选择器胶囊 */
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

/* 下拉菜单 */
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
    padding: 8px 12px 4px; font-size: 11px; color: #94a3b8;
    border-top: 1px solid #e2e8f0; margin-top: 4px;
}
```

#### 5.4 JS 交互逻辑

```javascript
let availableModels = [];
let currentModel = '';

async function initModelSelector() {
    const data = await loadModels();
    if (!data || !data.models.length) {
        // 降级：隐藏选择器
        return;
    }
    availableModels = data.models;
    currentModel = getPreferredModel(data.default);

    // 验证保存的模型是否仍可用
    if (!availableModels.find(m => m.id === currentModel)) {
        currentModel = data.default;
    }

    renderModelSelector();
    // 点击外部关闭
    document.addEventListener('click', (e) => {
        const menu = document.getElementById('model-menu');
        const capsule = document.getElementById('model-selector');
        if (menu && capsule && !capsule.contains(e.target) && !menu.contains(e.target)) {
            menu.style.display = 'none';
            capsule.classList.remove('open');
        }
    });
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
    if (menu.style.display === 'none') {
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
    setPreferredModel(modelId);
    renderModelSelector();
    const menu = document.getElementById('model-menu');
    menu.style.display = 'none';
    document.getElementById('model-selector').classList.remove('open');
}

function renderModelMenu() {
    const menu = document.getElementById('model-menu');
    // 按 provider 分组
    const providers = [...new Set(availableModels.map(m => m.provider))];
    menu.innerHTML = '';
    providers.forEach((provider, pi) => {
        if (pi > 0) {
            menu.innerHTML += '<div class="model-provider"></div>';
        }
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
            div.addEventListener('click', () => selectModel(model.id));
            menu.appendChild(div);
        });
    });
    // 底部提供商标签
    const model = availableModels.find(m => m.id === currentModel);
    if (model) {
        menu.innerHTML += `<div class="model-provider">${model.provider} 提供</div>`;
    }
}

// 在 window.onload 或页面初始化时调用
initModelSelector();
```

#### 5.5 修改 `sendMessage()`

将 `currentModel` 传入请求：

```javascript
async function sendMessage() {
    const text = msgInput.value.trim();
    if (!text) return;
    // ...
    const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, model: currentModel }),
    });
    // ...
}
```

## 数据流

```
用户点击胶囊 → 弹出菜单 → 选择模型 → localStorage.set + 更新胶囊显示
    ↓
发送消息 → POST /api/chat/stream {message, model}
    ↓
routes.py → agent.handle_message_stream(message, model_id=req.model)
    ↓
agent._agent_loop_stream → llm.chat_stream(messages, model_id=model_id)
    ↓
LLMClient._get_client(model_id) → 选择正确的 API key + base_url + model name
    ↓
OpenAI SDK 调用对应模型的 API
```

## 错误处理

- `/api/models` 加载失败 → 隐藏选择器，使用默认模型
- localStorage 中的模型已不存在于当前列表 → 回退到默认模型
- 无效 model_id → `_get_client()` 回退到默认模型
- 后续新增提供商的 API key 未配置 → API 调用时报错，前端显示错误信息

## 不变部分

- 现有 `/api/chat` 和 `/api/chat/stream` 行为保持兼容（`model` 字段有默认值 `""`）
- 没有模型选择时的行为与现在完全一致

## 后续扩展

添加 OpenAI GPT 模型只需在 `AVAILABLE_MODELS` 中加一条：

```python
{
    "id": "openai-gpt-5",
    "name": "GPT-5",
    "provider": "openai",
    "model": "gpt-5",
    "base_url": "https://api.openai.com/v1",
    "api_key": os.getenv("OPENAI_API_KEY", ""),
    "icon": "🤖",
    "description": "综合能力最强的模型",
}
```

## 测试要点

1. 页面加载时模型列表从 API 正确获取
2. 切换模型后胶囊显示更新
3. 刷新页面后模型选择保持（localStorage）
4. `/api/chat/stream` 携带正确的 model 参数
5. 不同模型调用不同的 API endpoint
6. `/api/models` 返回不含敏感信息
7. 模型菜单点击外部关闭
