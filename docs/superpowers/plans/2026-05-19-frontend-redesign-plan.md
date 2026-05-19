# 前端界面美化 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有暗色主题前端重构为极简白色风，提取 CSS 到独立文件，不动 JS 逻辑

**Architecture:** 新建 `src/web/static/style.css`（约 400 行）存放全部白主题 CSS；`index.html` 中 `<style>` 替换为 `<link>` 引用并添加 JetBrains Mono 字体 CDN；`app.py` 添加 `/static` 挂载

**Tech Stack:** 纯 CSS、FastAPI StaticFiles、Google Fonts CDN

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/web/static/style.css` | 新建 | 全部白主题 CSS（~400 行） |
| `src/web/templates/index.html` | 修改 | 替换 `<style>` 为 `<link>` + 字体 CDN |
| `src/web/app.py` | 修改 | 添加 `StaticFiles` 挂载 |

---

### Task 1: 创建静态目录和白主题 CSS

**Files:**
- Create: `src/web/static/style.css`

- [ ] **Step 1: 创建静态目录**

确认目录存在：
```bash
mkdir -p src/web/static
```

- [ ] **Step 2: 编写完整的白主题 CSS**

按以下内容编写 `src/web/static/style.css`：

```css
/* ═══ 1. Reset & Base ═══ */
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    background: #ffffff; color: #334155; height: 100vh; display: flex; flex-direction: column;
    font-size: 14px; line-height: 1.6;
}

/* ═══ 2. Header ═══ */
header {
    background: #ffffff; padding: 12px 20px; border-bottom: 1px solid #e2e8f0;
    display: flex; align-items: center; gap: 12px; flex-shrink: 0;
}
header h1 { font-size: 18px; font-weight: 600; color: #1e293b; }
header .current-tab { font-size: 13px; color: #6366f1; margin-left: 8px; }
#toggle-sidebar {
    background: none; border: 1px solid #e2e8f0; color: #64748b;
    font-size: 18px; cursor: pointer; padding: 4px 10px; border-radius: 8px;
    line-height: 1; transition: background 0.15s;
}
#toggle-sidebar:hover { background: #f1f5f9; color: #1e293b; }

/* ═══ 3. Layout ═══ */
#main-wrap { display: flex; flex: 1; overflow: hidden; }
#content { flex: 1; overflow-y: auto; padding: 20px; background: #ffffff; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }

/* ═══ 4. Sidebar ═══ */
#sidebar {
    background: #f8fafc; border-right: 1px solid #e2e8f0;
    width: 56px; flex-shrink: 0; overflow: hidden;
    transition: width 0.2s ease; display: flex; flex-direction: column; gap: 2px;
    padding: 8px 0;
}
#sidebar.open { width: 190px; }
#sidebar .tab-btn {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 16px; margin: 1px 6px; border: none; background: none; color: #94a3b8;
    cursor: pointer; font-size: 14px; white-space: nowrap;
    transition: all 0.15s; text-align: left; width: calc(100% - 12px);
    border-radius: 8px;
}
#sidebar .tab-btn:hover { background: #f1f5f9; color: #64748b; }
#sidebar .tab-btn.active { background: #eef2ff; color: #6366f1; font-weight: 600; }
#sidebar .tab-btn .icon { font-size: 18px; width: 22px; text-align: center; flex-shrink: 0; }
#sidebar.open .tab-btn { padding: 10px 14px; }

/* ═══ 5. Toolbar ═══ */
.toolbar {
    display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; align-items: center;
}
.toolbar input, .toolbar select, .toolbar button {
    padding: 8px 12px; border-radius: 10px; border: 1px solid #e2e8f0;
    background: #f8fafc; color: #334155; font-size: 13px; outline: none;
}
.toolbar input:focus, .toolbar select:focus { border-color: #6366f1; background: #fff; }
.toolbar button {
    cursor: pointer; background: #6366f1; border-color: #6366f1; color: #fff; font-weight: 600;
    transition: background 0.15s;
}
.toolbar button:hover { background: #4f46e5; }
.toolbar button.secondary { background: #f1f5f9; border-color: #e2e8f0; color: #334155; }
.toolbar button.secondary:hover { background: #e2e8f0; }

/* ═══ 6. Card ═══ */
.card {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 14px 16px; margin-bottom: 8px; cursor: pointer;
    transition: border-color 0.15s, box-shadow 0.15s;
}
.card:hover { border-color: #6366f1; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
.card .card-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.card .card-title { font-weight: 600; font-size: 14px; color: #1e293b; }
.card .card-meta { font-size: 12px; color: #94a3b8; margin-top: 4px; }
.card .card-preview { font-size: 13px; color: #64748b; margin-top: 6px; line-height: 1.5; }
.card .card-detail {
    display: none; margin-top: 12px; padding-top: 12px;
    border-top: 1px solid #e2e8f0; font-size: 13px; line-height: 1.7; color: #334155;
}
.card.expanded .card-detail { display: block; }

/* ═══ 7. Badge ═══ */
.badge {
    display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600;
}
.badge.github { background: #eef2ff; color: #6366f1; }
.badge.research { background: #ecfdf5; color: #10b981; }
.badge.conversation { background: #f1f5f9; color: #64748b; }
.badge.experience { background: #fef3c7; color: #d97706; }
.badge.decision { background: #ede9fe; color: #7c3aed; }

/* ═══ 8. Delete button ═══ */
.delete-btn {
    background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 16px;
    padding: 2px 6px; border-radius: 4px; flex-shrink: 0; transition: all 0.15s;
}
.delete-btn:hover { color: #ef4444; background: #fef2f2; }

#load-more { display: block; margin: 16px auto; }

/* ═══ 9. Toast ═══ */
.toast {
    position: fixed; top: 20px; left: 50%; transform: translateX(-50%) translateY(-10px);
    background: #1e293b; color: #fff;
    padding: 12px 20px; border-radius: 12px; font-size: 14px; z-index: 999;
    opacity: 0; transition: all 0.3s ease; max-width: 400px;
}
.toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
.toast.success { background: #10b981; }

/* ═══ 10. Status dots ═══ */
.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; }
.status-dot.sent { background: #10b981; }
.status-dot.pending { background: #f59e0b; }
.status-dot.failed { background: #ef4444; }

/* ═══ 11. Knowledge Graph ═══ */
#graph-canvas {
    width: 100%; height: 400px; border: 1px solid #e2e8f0; border-radius: 12px;
    background: #ffffff;
}

/* ═══ 12. Progress bar ═══ */
.prog-bar { height: 6px; background: #f1f5f9; border-radius: 3px; overflow: hidden; margin-top: 4px; }
.prog-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
.prog-fill.high { background: #10b981; }
.prog-fill.mid { background: #f59e0b; }
.prog-fill.low { background: #cbd5e1; }

/* ═══ 13. Chat ═══ */
#panel-chat { flex-direction: column; height: 100%; }
#panel-chat.active { display: flex; }
#chat-messages {
    flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 12px;
    margin-bottom: 16px; padding: 8px 4px;
}
#input-area { flex-shrink: 0; display: flex; gap: 10px; align-items: center; }

/* 消息气泡 */
.msg { max-width: 78%; padding: 10px 14px; line-height: 1.6; font-size: 14px; word-wrap: break-word; overflow-wrap: break-word; }
.msg.user {
    align-self: flex-end; background: #6366f1; color: #ffffff;
    border-radius: 16px 16px 4px 16px; box-shadow: 0 1px 3px rgba(99,102,241,0.2);
}
.msg.assistant {
    align-self: flex-start; background: #f8fafc; color: #334155;
    border-radius: 4px 16px 16px 16px; border: 1px solid #f1f5f9;
}
.loading { color: #94a3b8; font-style: italic; }

/* 输入区 */
#message {
    flex: 1; padding: 10px 16px; border-radius: 24px;
    border: 1px solid #e2e8f0; background: #f8fafc; color: #334155;
    resize: none; font-size: 14px; font-family: inherit; outline: none;
    transition: border-color 0.15s;
}
#message:focus { border-color: #6366f1; background: #ffffff; }
#message::placeholder { color: #cbd5e1; }
#send {
    padding: 10px 22px; border: none; border-radius: 20px;
    background: #6366f1; color: #fff; cursor: pointer;
    font-weight: 600; font-size: 14px; transition: background 0.15s;
}
#send:hover { background: #4f46e5; }
#send:disabled { opacity: 0.5; cursor: not-allowed; }

/* ═══ 14. Markdown 渲染样式 ═══ */
.msg.assistant h1, .msg.assistant h2, .msg.assistant h3, .msg.assistant h4 {
    margin: 12px 0 6px; color: #1e293b; font-weight: 600;
}
.msg.assistant h1 { font-size: 18px; }
.msg.assistant h2 { font-size: 16px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }
.msg.assistant h3 { font-size: 15px; }
.msg.assistant h4 { font-size: 14px; }
.msg.assistant p { margin: 4px 0; }
.msg.assistant code {
    background: #f1f5f9; padding: 2px 6px; border-radius: 4px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 13px; color: #e11d48;
}
.msg.assistant pre {
    background: #1e293b; border-radius: 8px; padding: 12px 14px;
    overflow-x: auto; margin: 8px 0;
}
.msg.assistant pre code { background: none; padding: 0; font-size: 13px; color: #e2e8f0; }
.msg.assistant table {
    border-collapse: collapse; margin: 8px 0; width: 100%;
}
.msg.assistant th, .msg.assistant td {
    border: 1px solid #e2e8f0; padding: 6px 12px; text-align: left;
}
.msg.assistant th { background: #f8fafc; font-weight: 600; color: #1e293b; }
.msg.assistant td { color: #334155; }
.msg.assistant blockquote {
    border-left: 3px solid #6366f1; padding: 4px 12px;
    color: #64748b; margin: 8px 0; background: #f8fafc;
    border-radius: 0 6px 6px 0;
}
.msg.assistant ul, .msg.assistant ol { padding-left: 24px; margin: 4px 0; }
.msg.assistant li { margin: 2px 0; }
.msg.assistant a { color: #6366f1; text-decoration: underline; }
.msg.assistant a:hover { color: #4f46e5; }
.msg.assistant img { max-width: 100%; border-radius: 6px; margin: 4px 0; }
.msg.assistant hr { border: none; border-top: 1px solid #e2e8f0; margin: 12px 0; }

/* ═══ 15. Tool steps panel ═══ */
.tool-steps {
    margin-top: 10px; font-size: 12px; color: #64748b;
    background: #f8fafc; border-radius: 8px;
    padding: 8px 12px; border: 1px solid #e2e8f0;
}
.tool-steps summary {
    cursor: pointer; color: #64748b; font-weight: 600; user-select: none;
}
.tool-steps summary:hover { color: #334155; }
.tool-steps .tool-list { margin-top: 6px; }
.tool-steps .tool-step { padding: 2px 0; }
.tool-steps .tool-step.running { color: #f59e0b; }
.tool-steps .tool-step.done { color: #10b981; }
.tool-steps .tool-step.error { color: #ef4444; }

/* ═══ 16. Email iframe ═══ */
.email-frame {
    width: 100%; height: 400px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fff;
}

/* ═══ 17. Modal ═══ */
.modal-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 1000;
    display: flex; align-items: center; justify-content: center;
}
.modal-box {
    background: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px;
    padding: 24px; max-width: 400px; width: 90%; box-shadow: 0 20px 60px rgba(0,0,0,0.1);
}
.modal-box h3 { margin-bottom: 12px; font-size: 16px; color: #1e293b; }
.modal-box p { color: #64748b; font-size: 14px; margin-bottom: 20px; }
.modal-box .modal-actions { display: flex; gap: 10px; justify-content: flex-end; }
.modal-box .modal-actions button {
    padding: 8px 16px; border-radius: 10px; border: 1px solid #e2e8f0;
    font-size: 13px; cursor: pointer; font-weight: 600;
}
.modal-box .modal-actions button.secondary { background: #f1f5f9; color: #334155; }
.modal-box .modal-actions button:not(.secondary) { background: #ef4444; color: #fff; border-color: #ef4444; }

/* ═══ 18. Scrollbar ═══ */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
```

- [ ] **Step 3: 验证 CSS 文件存在且无语法错误**

Run: `python -c "with open('src/web/static/style.css') as f: content=f.read(); print(f'CSS file: {len(content)} chars')"`
Expected: `CSS file: 8000+ chars`

- [ ] **Step 4: Commit**

```bash
git add src/web/static/style.css
git commit -m "feat: 添加白主题 style.css（全局/侧边栏/聊天/卡片/MD 渲染）"
```

---

### Task 2: 修改 app.py 挂载静态文件

**Files:**
- Modify: `src/web/app.py:17`（在 `app.include_router(router)` 之后添加）

- [ ] **Step 1: 添加 StaticFiles 挂载**

在 `app.include_router(router)` 之后添加一行：

```python
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
```

注意：`StaticFiles` 已在文件顶部导入（第 4 行），无需额外 import。

- [ ] **Step 2: 验证静态文件服务**

重启服务器后：
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/static/style.css
```
Expected: `200`

- [ ] **Step 3: Commit**

```bash
git add src/web/app.py
git commit -m "feat: 挂载 /static 静态文件目录"
```

---

### Task 3: 修改 index.html 替换内联 CSS

**Files:**
- Modify: `src/web/templates/index.html`（`<style>` 块替换为 `<link>` + 添加字体 CDN）

- [ ] **Step 1: 添加 JetBrains Mono 字体 CDN**

在 `<title>` 之后、`<style>` 之前添加：

```html
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
```

- [ ] **Step 2: 替换整个 `<style>...</style>` 块为外部引用**

找到从 `<style>` 到 `</style>` 的全部内容（原第 7-205 行区域），替换为：

```html
    <link rel="stylesheet" href="/static/style.css">
```

- [ ] **Step 3: 验证 HTML 结构完整**

```bash
python -c "
with open('src/web/templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()
assert '<link rel=\"stylesheet\" href=\"/static/style.css\">' in html
assert '<style>' not in html
print('OK: inline <style> replaced with <link>')
"
```

Expected: `OK: inline <style> replaced with <link>`

- [ ] **Step 4: Commit**

```bash
git add src/web/templates/index.html
git commit -m "feat: 内联 CSS 替换为外部 style.css 引用 + JetBrains Mono 字体"
```

---

### Task 4: 集成测试 — 验证静态文件和页面加载

**Files:**
- Modify: `tests/test_streaming.py`（新增 2 个测试）

- [ ] **Step 1: 添加静态文件测试和页面加载测试**

在 `tests/test_streaming.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_static_css_served(client):
    """验证静态 CSS 文件可访问。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/static/style.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers.get("content-type", "")
        assert len(resp.text) > 1000


@pytest.mark.asyncio
async def test_index_page_loads(client):
    """验证主页 HTML 可加载且引用外部 CSS。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/")
        assert resp.status_code == 200
        html = resp.text
        assert '/static/style.css' in html
        assert '<style>' not in html  # 确认无内联 CSS
```

- [ ] **Step 2: 运行新增测试**

```bash
pytest tests/test_streaming.py::test_static_css_served tests/test_streaming.py::test_index_page_loads -v
```
Expected: 2 PASSED

- [ ] **Step 3: 运行全部流式测试确认无回归**

```bash
pytest tests/test_streaming.py -v
```
Expected: 5 PASSED（3 原有 + 2 新增）

- [ ] **Step 4: Commit**

```bash
git add tests/test_streaming.py
git commit -m "test: 添加静态 CSS 和页面加载集成测试"
```

---

### Task 5: 启动服务器手动验证

- [ ] **Step 1: 启动开发服务器**

```bash
python run.py
```

- [ ] **Step 2: 浏览器验证清单**

打开 `http://localhost:8000`，逐一验证：

1. 页面白底加载正常，无暗色残留
2. 所有 6 个 Tab 切换正常（聊天/报告/邮件/记忆/图谱/Skills）
3. 聊天消息气泡样式正常（用户紫色、助手浅灰）
4. Markdown 渲染样式正常（代码块深色、表格有条纹）
5. 发送消息流畅式输出正常
6. 工具调用折叠面板样式正常
7. 卡片 hover 效果正常
8. Toast 弹出样式正常
9. Modal 弹窗样式正常
10. 字体加载正常（代码块使用 JetBrains Mono）

- [ ] **Step 3: 如有问题，修复并追加 commit**

---

## 变更文件汇总

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/web/static/style.css` | 新建 | 完整白主题 CSS（~400 行） |
| `src/web/app.py` | 修改 | +1 行：挂载 `/static` |
| `src/web/templates/index.html` | 修改 | 替换 `<style>` 为 `<link>` + 字体 CDN |
| `tests/test_streaming.py` | 修改 | +2 测试：静态 CSS 和页面加载 |
