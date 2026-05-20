# Agent 报告自动持久化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agent 执行定时/手动触发任务后，将最终摘要文本自动保存到 agent_reports 表，前端报告 Tab 可查看。

**Architecture:** 新增 agent_reports 表 + LongTermMemory.save_agent_report()；handle_scheduled 和 handle_scheduled_stream 两个方法在最终文本产生时调用保存；/api/reports 系列端点增加 agent_report 类型。

**Tech Stack:** Python/SQLite/FastAPI（后端），vanilla JS（前端）

---

### Task 1: 数据层 — 新增 agent_reports 表和 save_agent_report 方法

**Files:**
- Modify: `src/db/models.py`
- Modify: `src/memory/long_term.py`

- [ ] **Step 1: 在 SCHEMA 中新增 agent_reports 表**

在 `src/db/models.py` 的 SCHEMA 字符串中，`pending_emails` 表定义之后（第 95 行之后，`"""` 结束符之前）插入：

```sql
CREATE TABLE IF NOT EXISTS agent_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    session_id TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 2: 重新初始化数据库以创建新表**

Run: `python -c "from src.db.models import init_db; init_db(); print('OK')"`

Expected: `OK`

- [ ] **Step 3: 在 LongTermMemory 中新增 save_agent_report 方法**

在 `src/memory/long_term.py` 的 `LongTermMemory` 类末尾（第 131 行 `lts = LongTermMemory()` 之前）添加：

```python
    def save_agent_report(self, trigger: str, title: str, content: str, session_id: str) -> int:
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO agent_reports (trigger, title, content, session_id) VALUES (?, ?, ?, ?)",
            (trigger, title, content, session_id),
        )
        conn.commit()
        report_id = cursor.lastrowid
        conn.close()
        return report_id
```

- [ ] **Step 4: 验证导入和方法可用**

Run: `python -c "from src.memory.long_term import lts; assert hasattr(lts, 'save_agent_report'); print('OK')"`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/db/models.py src/memory/long_term.py
git commit -m "feat: 新增 agent_reports 表和 save_agent_report 方法

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Agent — handle_scheduled 保存最终摘要

**Files:**
- Modify: `src/core/agent.py:65-77`

- [ ] **Step 1: 修改 handle_scheduled 方法，在返回前保存报告**

将 `handle_scheduled` 方法（第 65-77 行）替换为：

```python
    async def handle_scheduled(self, trigger: str) -> str:
        """主动触发：处理定时任务。"""
        context = retrieve_relevant_context(trigger)

        initial = SCHEDULED_PROMPTS.get(trigger, f"执行任务：{trigger}")
        agent_logger.info("[SYSTEM] 定时触发: %s", trigger)
        self.short_term.add("system", initial)

        result = await self._agent_loop(
            trigger=trigger,
            initial_context=context,
            max_rounds=8,
        )

        # 保存最终摘要为报告
        if result and result.strip():
            title = result.strip().split("\n")[0][:80]
            lts.save_agent_report(
                trigger=trigger,
                title=title,
                content=result.strip(),
                session_id=self.session_id,
            )

        return result
```

- [ ] **Step 2: 验证 handle_scheduled 仍可正常调用**

Run: `pytest tests/test_agent.py::test_agent_scheduled -v`

Expected: PASS（LLM 调用后保存到 agent_reports 表不抛异常）

- [ ] **Step 3: Commit**

```bash
git add src/core/agent.py
git commit -m "feat: handle_scheduled 自动保存最终摘要到 agent_reports

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: Agent — handle_scheduled_stream 累积 text 并保存

**Files:**
- Modify: `src/core/agent.py:79-101`

- [ ] **Step 1: 修改 handle_scheduled_stream，增加 text 累积和保存逻辑**

将 `handle_scheduled_stream` 方法（第 79-101 行）替换为：

```python
    async def handle_scheduled_stream(self, trigger: str, model_id: str = ""):
        """流式版 handle_scheduled，返回 async generator，yield SSE 事件 dict。"""
        try:
            context = retrieve_relevant_context(trigger)

            initial = SCHEDULED_PROMPTS.get(trigger, f"执行任务：{trigger}")
            agent_logger.info("[SYSTEM] 流式触发: %s", trigger)
            self.short_term.add("system", initial)

            text_buffer = ""
            async for event in self._agent_loop_stream(
                trigger=trigger,
                initial_context=context,
                max_rounds=8,
                model_id=model_id,
            ):
                if event["type"] == "text":
                    text_buffer += event["content"]
                elif event["type"] == "tool_start":
                    text_buffer = ""  # 工具调用开始，清空中间文本
                elif event["type"] == "done":
                    if text_buffer.strip():
                        title = text_buffer.strip().split("\n")[0][:80]
                        lts.save_agent_report(
                            trigger=trigger,
                            title=title,
                            content=text_buffer.strip(),
                            session_id=self.session_id,
                        )
                yield event
        except Exception as e:
            yield {"type": "error", "message": f"处理失败: {str(e)}"}
        finally:
            self._persist_and_clear()
            result = await commit_and_push()
            if result:
                agent_logger.info("[SYSTEM] Git: %s", result)
```

- [ ] **Step 2: 验证方法签名不变且可导入**

Run: `python -c "from src.core.agent import Agent; a = Agent(); import inspect; assert inspect.isasyncgenfunction(a.handle_scheduled_stream); print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/core/agent.py
git commit -m "feat: handle_scheduled_stream 流式累积文本并保存最终摘要

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: API — /api/reports 系列端点增加 agent_report 类型

**Files:**
- Modify: `src/web/routes.py`

- [ ] **Step 1: 修改 list_reports 增加 agent_report 查询**

在 `list_reports` 函数中（`src/web/routes.py` 第 115-150 行），在 research 查询块之后、`conn.close()` 之前，添加 agent_report 查询：

```python
    if not type or type == "agent_report":
        rows = conn.execute(
            "SELECT id, trigger, title, content, session_id, created_at FROM agent_reports ORDER BY created_at DESC"
        ).fetchall()
        for r in rows:
            items.append({
                "id": f"agent_report_{r['id']}",
                "type": "agent_report",
                "title": r["title"],
                "preview": (r["content"] or "")[:200],
                "created_at": r["created_at"],
            })
```

- [ ] **Step 2: 修改 get_report 处理 agent_report 前缀**

在 `get_report` 函数（第 153 行起）中，在现有的 `if prefix == "research":` 块之后、`conn.close()` 之前添加：

```python
    if prefix == "agent_report":
        row = conn.execute(
            "SELECT id, trigger, title, content, session_id, created_at FROM agent_reports WHERE id = ?",
            (rid,),
        ).fetchone()
        conn.close()
        if not row:
            return JSONResponse({"error": "报告不存在"}, status_code=404)
        return {
            "id": f"agent_report_{row['id']}",
            "type": "agent_report",
            "title": row["title"],
            "content": row["content"] or "",
            "created_at": row["created_at"],
        }
```

注意：需要将 `conn.close()` 移到 prefix == "agent_report" 的分支中，不能 double-close。查看原始代码结构，每个 prefix 分支都自己 `conn.close()` 后 return，所以只需在 `if prefix == "research":` 块之后插入 agent_report 块即可。

- [ ] **Step 3: 修改 delete_report 处理 agent_report 前缀**

在 `delete_report` 函数（第 206 行起）中，在 `elif prefix == "research":` 之后添加：

```python
    elif prefix == "agent_report":
        conn.execute("DELETE FROM agent_reports WHERE id = ?", (rid,))
```

- [ ] **Step 4: 验证 API 路由无语法错误**

Run: `python -c "from src.web.routes import router; paths = [r.path for r in router.routes]; print('Routes OK,', len(paths), 'paths')"`

Expected: `Routes OK, N paths`

- [ ] **Step 5: Commit**

```bash
git add src/web/routes.py
git commit -m "feat: /api/reports 端点增加 agent_report 类型支持

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: 前端 — 报告 Tab 增加学习周报筛选和渲染

**Files:**
- Modify: `src/web/templates/index.html`

- [ ] **Step 1: 在报告类型筛选下拉框增加"学习周报"选项**

找到 `<select id="report-type-filter">`（约第 60 行），在 research 选项之后添加：

```html
                        <option value="agent_report">学习周报</option>
```

- [ ] **Step 2: 修改报告列表渲染，支持 agent_report 的 badge 和标题**

找到 `renderReportList` 函数中的 badge 渲染逻辑（约第 568-572 行 `cardHeader` 中的 badge 部分）。将：

```javascript
                    <span class="badge ${item.type}">${item.type === 'github' ? 'GitHub' : '研究'}</span>
```

改为：

```javascript
                    <span class="badge ${item.type}">${item.type === 'github' ? 'GitHub' : item.type === 'research' ? '研究' : '周报'}</span>
```

- [ ] **Step 3: 在 CSS 已有 badge 样式中确认 agent_report 有对应颜色（无需改动验证）**

已有的 badge 颜色：`.badge.github`、`.badge.research`、`.badge.conversation` 等。`agent_report` 会匹配到哪个？需要新增一个。在 `style.css` 末尾追加：

```css
.badge.agent_report { background: #fff7ed; color: #ea580c; }
```

- [ ] **Step 4: 验证 HTML 结构**

Run: `python -c "with open('src/web/templates/index.html', 'r', encoding='utf-8') as f: content = f.read(); assert 'agent_report' in content; print('OK')"`

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/web/templates/index.html src/web/static/style.css
git commit -m "feat: 报告 Tab 新增学习周报筛选和渲染

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: 测试与集成验证

**Files:**
- Modify: `tests/test_actions.py`（可选，追加测试）

- [ ] **Step 1: 编写 agent_reports API 测试**

在 `tests/test_actions.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_agent_reports_in_report_list():
    """验证报告列表包含 agent_report 类型。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        # 请求全部类型
        resp = await ac.get("/api/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        # 验证 items 中可能有 agent_report 类型（可能为空）
        assert isinstance(data["items"], list)

        # 只请求 agent_report 类型
        resp = await ac.get("/api/reports?type=agent_report")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data


@pytest.mark.asyncio
async def test_agent_report_detail_404():
    """验证不存在的 agent_report 详情返回 404。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/reports/agent_report_99999")
        assert resp.status_code == 404
```

- [ ] **Step 2: 运行新增测试 + 已有测试**

Run: `pytest tests/test_actions.py -v`

Expected: 7 passed（原有 5 + 新增 2）

- [ ] **Step 3: 启动服务器验证端到端流程**

Run: `python -c "from src.web.app import app; from src.core.agent import Agent; from src.db.models import init_db; init_db(); print('All imports OK, DB ready')"`

Expected: `All imports OK, DB ready`

- [ ] **Step 4: Commit**

```bash
git add tests/test_actions.py
git commit -m "test: 新增 agent_report API 测试

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### 手动验证清单

启动 `python run.py`，在浏览器中：
1. 切换到"操作"Tab，点击"周期检查"执行
2. 等待流式面板显示完成
3. 切换到"报告"Tab，筛选下拉选择"学习周报"
4. 确认看到刚生成的周报卡片，点击展开可查看全文
5. 切换到"报告"Tab，选择"全部类型"，确认周报和其他类型报告混合显示
