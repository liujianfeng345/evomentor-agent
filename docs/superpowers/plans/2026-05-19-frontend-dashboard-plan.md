# 前端仪表盘实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将单页聊天界面扩展为多 Tab 仪表盘，支持在前端查看聊天、报告、邮件、记忆、知识图谱和 Skills。

**Architecture:** 纯 Vanilla JS + REST API，后端在现有 `routes.py` 中新增 10 个只读/删除端点，前端在一个 HTML 文件中实现侧边栏导航 + 6 个 Tab 面板。零新依赖。

**Tech Stack:** FastAPI + SQLite + Vanilla JS + Canvas API

---

### Task 1: API — 报告端点（列表 / 详情 / 删除）

**Files:**
- Modify: `src/web/routes.py`

**说明：** 报告列表合并 `github_analyses` 和 `research_findings` 两张表，按时间倒序排列。用类型前缀 `github_` / `research_` 区分 ID。

- [ ] **Step 1: 在 routes.py 中新增请求模型和报告端点**

在 `src/web/routes.py` 末尾追加以下代码：

```python
"""报告与记忆相关的 API 端点。"""
from src.db.models import get_connection


class DeleteResponse(BaseModel):
    ok: bool


# ─── 报告 ───────────────────────────────────────────────

@router.get("/api/reports")
async def list_reports(limit: int = 20, offset: int = 0, type: str = ""):
    """合并 github_analyses 和 research_findings，按时间倒序。"""
    conn = get_connection()
    items: list[dict] = []

    if not type or type == "github":
        rows = conn.execute(
            "SELECT id, repo_name, findings, analyzed_at FROM github_analyses ORDER BY analyzed_at DESC"
        ).fetchall()
        for r in rows:
            items.append({
                "id": f"github_{r['id']}",
                "type": "github",
                "title": r["repo_name"],
                "preview": (r["findings"] or "")[:200],
                "created_at": r["analyzed_at"],
            })

    if not type or type == "research":
        rows = conn.execute(
            "SELECT id, topic, source_type, summary, found_at FROM research_findings ORDER BY found_at DESC"
        ).fetchall()
        for r in rows:
            items.append({
                "id": f"research_{r['id']}",
                "type": "research",
                "title": f"{r['topic']} ({r['source_type']})",
                "preview": (r["summary"] or "")[:200],
                "created_at": r["found_at"],
            })

    conn.close()
    items.sort(key=lambda x: x["created_at"] or "", reverse=True)
    total = len(items)
    return {"items": items[offset: offset + limit], "total": total}


@router.get("/api/reports/{report_id}")
async def get_report(report_id: str):
    """获取单条报告详情。ID 格式: github_1 或 research_2。"""
    conn = get_connection()
    parts = report_id.split("_", 1)
    if len(parts) != 2:
        conn.close()
        return JSONResponse({"error": "无效的报告 ID"}, status_code=400)
    prefix, rid = parts[0], int(parts[1])

    if prefix == "github":
        row = conn.execute(
            "SELECT id, repo_name, commit_sha, findings, suggestions, analyzed_at FROM github_analyses WHERE id = ?",
            (rid,),
        ).fetchone()
        conn.close()
        if not row:
            return JSONResponse({"error": "报告不存在"}, status_code=404)
        return {
            "id": f"github_{row['id']}",
            "type": "github",
            "title": row["repo_name"],
            "commit_sha": row["commit_sha"],
            "content": row["findings"] or "",
            "suggestions": row["suggestions"] or "",
            "created_at": row["analyzed_at"],
        }

    if prefix == "research":
        row = conn.execute(
            "SELECT id, topic, source_type, url, summary, found_at FROM research_findings WHERE id = ?",
            (rid,),
        ).fetchone()
        conn.close()
        if not row:
            return JSONResponse({"error": "报告不存在"}, status_code=404)
        return {
            "id": f"research_{row['id']}",
            "type": "research",
            "title": f"{row['topic']} ({row['source_type']})",
            "url": row["url"],
            "content": row["summary"] or "",
            "created_at": row["found_at"],
        }

    conn.close()
    return JSONResponse({"error": "未知报告类型"}, status_code=400)


@router.delete("/api/reports/{report_id}", response_model=DeleteResponse)
async def delete_report(report_id: str):
    """删除报告。"""
    conn = get_connection()
    parts = report_id.split("_", 1)
    if len(parts) != 2:
        conn.close()
        return JSONResponse({"error": "无效的报告 ID"}, status_code=400)
    prefix, rid = parts[0], int(parts[1])

    if prefix == "github":
        conn.execute("DELETE FROM github_analyses WHERE id = ?", (rid,))
    elif prefix == "research":
        conn.execute("DELETE FROM research_findings WHERE id = ?", (rid,))
    else:
        conn.close()
        return JSONResponse({"error": "未知报告类型"}, status_code=400)
    conn.commit()
    conn.close()
    return {"ok": True}
```

同时需要在文件顶部 import 部分加入 `JSONResponse`：

```python
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
```

替换原有 import 行：
```python
from fastapi import APIRouter, Request
```

改为：
```python
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
```

`DeleteResponse` 模型应放在已有模型类之后。

- [ ] **Step 2: 启动服务并测试报告列表接口**

```bash
curl -s http://localhost:8000/api/reports?limit=3 | python -m json.tool
```

- [ ] **Step 3: 提交**

```bash
git add src/web/routes.py
git commit -m "feat: 添加报告列表、详情、删除 API 端点

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: API — 邮件端点（列表 / 详情 / 删除 / 发送）

**Files:**
- Modify: `src/web/routes.py`

- [ ] **Step 1: 在 routes.py 末尾追加邮件端点**

```python
# ─── 邮件 ───────────────────────────────────────────────

@router.get("/api/emails")
async def list_emails(limit: int = 20, offset: int = 0, status: str = ""):
    """获取邮件列表，可按状态筛选。"""
    conn = get_connection()
    if status and status in ("sent", "pending", "failed"):
        rows = conn.execute(
            "SELECT id, subject, body, status, scheduled_at, sent_at FROM pending_emails WHERE status = ? ORDER BY scheduled_at DESC LIMIT ? OFFSET ?",
            (status, limit, offset),
        ).fetchall()
        total_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM pending_emails WHERE status = ?", (status,)
        ).fetchone()
    else:
        rows = conn.execute(
            "SELECT id, subject, body, status, scheduled_at, sent_at FROM pending_emails ORDER BY scheduled_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total_row = conn.execute("SELECT COUNT(*) as cnt FROM pending_emails").fetchone()
    conn.close()
    items = [
        {
            "id": r["id"],
            "subject": r["subject"],
            "preview": (r["body"] or "")[:200],
            "status": r["status"],
            "scheduled_at": r["scheduled_at"],
            "sent_at": r["sent_at"],
        }
        for r in rows
    ]
    return {"items": items, "total": total_row["cnt"]}


@router.post("/api/emails/send")
async def send_emails():
    """手动触发发送全部待发邮件。必须放在 /{email_id} 之前避免路由冲突。"""
    try:
        agent = get_agent()
        result = await agent.handle_message("请使用 send_email 工具立即发送所有待发邮件。")
        return {"ok": True, "result": result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/emails/{email_id}")
async def get_email(email_id: int):
    """获取邮件详情，含完整 HTML body。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, subject, body, status, scheduled_at, sent_at FROM pending_emails WHERE id = ?",
        (email_id,),
    ).fetchone()
    conn.close()
    if not row:
        return JSONResponse({"error": "邮件不存在"}, status_code=404)
    return dict(row)


@router.delete("/api/emails/{email_id}", response_model=DeleteResponse)
async def delete_email(email_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM pending_emails WHERE id = ?", (email_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
```

- [ ] **Step 2: 启动服务并测试邮件列表接口**

```bash
curl -s http://localhost:8000/api/emails | python -m json.tool
```

- [ ] **Step 3: 提交**

```bash
git add src/web/routes.py
git commit -m "feat: 添加邮件列表、详情、删除、发送 API 端点

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: API — 记忆端点（列表 / 删除）

**Files:**
- Modify: `src/web/routes.py`

- [ ] **Step 1: 在 routes.py 末尾追加记忆端点**

```python
# ─── 记忆 ───────────────────────────────────────────────

@router.get("/api/memories")
async def list_memories(limit: int = 20, offset: int = 0, type: str = "", search: str = ""):
    """合并 conversations、experiences、agent_decisions 三张表。"""
    conn = get_connection()
    items: list[dict] = []

    def _match(text: str) -> bool:
        return not search or search.lower() in text.lower()

    if not type or type == "conversation":
        rows = conn.execute(
            "SELECT id, role, content, topic_tags, intent, created_at FROM conversations ORDER BY created_at DESC LIMIT 500"
        ).fetchall()
        for r in rows:
            text = f"{r['role']}: {r['content'] or ''}"
            if not _match(text):
                continue
            items.append({
                "id": f"conv_{r['id']}",
                "type": "conversation",
                "title": text[:100],
                "preview": text[:200],
                "tags": r["topic_tags"] or "[]",
                "role": r["role"],
                "intent": r["intent"] or "",
                "created_at": r["created_at"],
            })

    if not type or type == "experience":
        rows = conn.execute(
            "SELECT id, category, title, content, source, confidence, created_at FROM experiences ORDER BY created_at DESC LIMIT 500"
        ).fetchall()
        for r in rows:
            text = f"{r['category']}: {r['title']} — {r['content'] or ''}"
            if not _match(text):
                continue
            items.append({
                "id": f"exp_{r['id']}",
                "type": "experience",
                "title": r["title"],
                "preview": text[:200],
                "category": r["category"],
                "source": r["source"],
                "confidence": r["confidence"],
                "created_at": r["created_at"],
            })

    if not type or type == "decision":
        rows = conn.execute(
            "SELECT id, trigger, tool_calls, reasoning, outcome, created_at FROM agent_decisions ORDER BY created_at DESC LIMIT 500"
        ).fetchall()
        for r in rows:
            text = f"触发: {r['trigger']} | 工具: {r['tool_calls']} | 结果: {(r['outcome'] or '')[:100]}"
            if not _match(text):
                continue
            items.append({
                "id": f"dec_{r['id']}",
                "type": "decision",
                "title": f"决策: {r['trigger']} → {r['tool_calls']}",
                "preview": text[:200],
                "trigger_name": r["trigger"],
                "tool_calls": r["tool_calls"],
                "reasoning": r["reasoning"],
                "outcome": r["outcome"],
                "created_at": r["created_at"],
            })

    conn.close()
    items.sort(key=lambda x: x["created_at"] or "", reverse=True)
    total = len(items)
    return {"items": items[offset: offset + limit], "total": total}


@router.delete("/api/memories/{memory_id}", response_model=DeleteResponse)
async def delete_memory(memory_id: str):
    """删除记忆。ID 格式: conv_1 / exp_2 / dec_3。"""
    conn = get_connection()
    parts = memory_id.split("_", 1)
    if len(parts) != 2:
        conn.close()
        return JSONResponse({"error": "无效的记忆 ID"}, status_code=400)
    prefix, mid = parts[0], int(parts[1])

    table_map = {"conv": "conversations", "exp": "experiences", "dec": "agent_decisions"}
    table = table_map.get(prefix)
    if not table:
        conn.close()
        return JSONResponse({"error": "未知记忆类型"}, status_code=400)
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (mid,))
    conn.commit()
    conn.close()
    return {"ok": True}
```

- [ ] **Step 2: 启动服务并测试记忆列表接口**

```bash
curl -s "http://localhost:8000/api/memories?limit=5" | python -m json.tool
```

- [ ] **Step 3: 提交**

```bash
git add src/web/routes.py
git commit -m "feat: 添加记忆列表、删除 API 端点

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: API — 知识图谱端点

**Files:**
- Modify: `src/web/routes.py`

- [ ] **Step 1: 在 routes.py 末尾追加知识图谱端点**

```python
# ─── 知识图谱 ────────────────────────────────────────────

@router.get("/api/graph")
async def get_graph():
    """返回知识图谱的节点和边。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, topic, proficiency, parent_topic FROM user_knowledge_graph WHERE parent_topic != 'preference' ORDER BY proficiency DESC"
    ).fetchall()
    conn.close()

    nodes: list[dict] = []
    edges: list[dict] = []
    topic_ids: dict[str, int] = {}

    for r in rows:
        tid = r["id"]
        topic_ids[r["topic"]] = tid
        nodes.append({
            "id": tid,
            "label": r["topic"],
            "proficiency": r["proficiency"],
        })
        if r["parent_topic"] and r["parent_topic"] != "preference":
            edges.append({
                "from": r["parent_topic"],
                "to": r["topic"],
            })

    # 为 edges 中的 parent_topic 补充不在列表中的节点
    for edge in edges:
        if edge["from"] not in topic_ids:
            nodes.append({
                "id": -1,
                "label": edge["from"],
                "proficiency": 0,
            })
            topic_ids[edge["from"]] = -1

    # 将 edge 的 label 转为 id
    resolved_edges = []
    for edge in edges:
        from_id = topic_ids.get(edge["from"])
        to_id = topic_ids.get(edge["to"])
        if from_id is not None and to_id is not None:
            resolved_edges.append({"from": from_id, "to": to_id})

    return {"nodes": nodes, "edges": resolved_edges}
```

- [ ] **Step 2: 测试知识图谱接口**

```bash
curl -s http://localhost:8000/api/graph | python -m json.tool
```

- [ ] **Step 3: 提交**

```bash
git add src/web/routes.py
git commit -m "feat: 添加知识图谱 API 端点

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: API — Skills 端点（列表 / 详情 / 删除）

**Files:**
- Modify: `src/web/routes.py`

- [ ] **Step 1: 在 routes.py 末尾追加 Skills 端点**

```python
# ─── Skills ──────────────────────────────────────────────

@router.get("/api/skills")
async def list_skills(limit: int = 20, offset: int = 0):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, trigger_condition, version, active, usage_count, success_rate, file_path, created_at, updated_at FROM skills ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    total_row = conn.execute("SELECT COUNT(*) as cnt FROM skills").fetchone()
    conn.close()
    items = [dict(r) for r in rows]
    return {"items": items, "total": total_row["cnt"]}


@router.get("/api/skills/{skill_id}")
async def get_skill_detail(skill_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
    conn.close()
    if not row:
        return JSONResponse({"error": "Skill 不存在"}, status_code=404)
    data = dict(row)
    # 读取 Markdown 文件内容
    file_path = data.get("file_path", "")
    if file_path and os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data["file_content"] = f.read()
    else:
        data["file_content"] = ""
    return data


@router.delete("/api/skills/{skill_id}", response_model=DeleteResponse)
async def delete_skill(skill_id: int):
    conn = get_connection()
    row = conn.execute("SELECT file_path FROM skills WHERE id = ?", (skill_id,)).fetchone()
    if row and row["file_path"] and os.path.exists(row["file_path"]):
        os.remove(row["file_path"])
    conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
    conn.commit()
    conn.close()
    return {"ok": True}
```

需要在文件顶部已有 import 区域追加 `os` 模块：

```python
import os
```

- [ ] **Step 2: 测试 Skills 列表接口**

```bash
curl -s http://localhost:8000/api/skills | python -m json.tool
```

- [ ] **Step 3: 提交**

```bash
git add src/web/routes.py
git commit -m "feat: 添加 Skills 列表、详情、删除 API 端点

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: API — 手动反思触发端点

**Files:**
- Modify: `src/web/routes.py`

- [ ] **Step 1: 在 routes.py 末尾追加反思端点**

```python
# ─── 反思 ────────────────────────────────────────────────

@router.post("/api/reflect")
async def trigger_reflect():
    """手动触发反思。"""
    try:
        agent = get_agent()
        result = await agent.handle_scheduled("reflect")
        return {"ok": True, "result": result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
```

- [ ] **Step 2: 提交**

```bash
git add src/web/routes.py
git commit -m "feat: 添加手动反思触发 API 端点

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: 前端 — 页面骨架与侧边栏布局

**Files:**
- Modify: `src/web/templates/index.html`

**说明：** 完整重写 HTML，先建好布局骨架（侧边栏 + 内容区 + 6 个空 Tab 面板），后续 Task 逐个填充 Tab 内容。

- [ ] **Step 1: 写入完整的 HTML 骨架、CSS 和侧边栏 JS**

`index.html` 完整内容：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evomentor — 个人学习助手</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1a1a2e; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column;
        }
        /* Header */
        header {
            background: #16213e; padding: 12px 20px; border-bottom: 1px solid #0f3460;
            display: flex; align-items: center; gap: 12px; flex-shrink: 0;
        }
        header h1 { font-size: 18px; font-weight: 600; }
        header .current-tab { font-size: 13px; color: #e94560; margin-left: 8px; }
        #toggle-sidebar {
            background: none; border: 1px solid #0f3460; color: #e0e0e0;
            font-size: 18px; cursor: pointer; padding: 4px 10px; border-radius: 4px;
            line-height: 1;
        }
        #toggle-sidebar:hover { background: #0f3460; }

        /* 主体 */
        #main-wrap { display: flex; flex: 1; overflow: hidden; }

        /* 侧边栏 */
        #sidebar {
            background: #16213e; border-right: 1px solid #0f3460;
            width: 48px; flex-shrink: 0; overflow: hidden;
            transition: width 0.2s ease; display: flex; flex-direction: column; gap: 2px;
            padding: 8px 0;
        }
        #sidebar.open { width: 170px; }
        #sidebar .tab-btn {
            display: flex; align-items: center; gap: 10px;
            padding: 10px 14px; border: none; background: none; color: #aaa;
            cursor: pointer; font-size: 14px; white-space: nowrap;
            transition: background 0.15s; text-align: left; width: 100%;
        }
        #sidebar .tab-btn:hover { background: #1a1a2e; color: #e0e0e0; }
        #sidebar .tab-btn.active { background: #0f3460; color: #fff; font-weight: 600; }
        #sidebar .tab-btn .icon { font-size: 16px; width: 20px; text-align: center; flex-shrink: 0; }

        /* 内容区 */
        #content { flex: 1; overflow-y: auto; padding: 20px; }
        .tab-panel { display: none; }
        .tab-panel.active { display: block; }

        /* 通用组件 */
        .toolbar {
            display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; align-items: center;
        }
        .toolbar input, .toolbar select, .toolbar button {
            padding: 8px 12px; border-radius: 6px; border: 1px solid #0f3460;
            background: #1a1a2e; color: #e0e0e0; font-size: 13px;
        }
        .toolbar button {
            cursor: pointer; background: #e94560; border-color: #e94560; color: #fff; font-weight: 600;
        }
        .toolbar button:hover { background: #d63851; }
        .toolbar button.secondary { background: #0f3460; border-color: #0f3460; }

        .card {
            background: #16213e; border: 1px solid #0f3460; border-radius: 8px;
            padding: 14px 16px; margin-bottom: 10px; cursor: pointer; transition: border-color 0.15s;
        }
        .card:hover { border-color: #e94560; }
        .card .card-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
        .card .card-title { font-weight: 600; font-size: 14px; color: #fff; }
        .card .card-meta { font-size: 12px; color: #888; margin-top: 4px; }
        .card .card-preview { font-size: 13px; color: #aaa; margin-top: 6px; line-height: 1.5; }
        .card .card-detail { display: none; margin-top: 12px; padding-top: 12px; border-top: 1px solid #0f3460; font-size: 13px; line-height: 1.7; }
        .card.expanded .card-detail { display: block; }
        .badge {
            display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px;
            font-weight: 600;
        }
        .badge.github { background: #238636; color: #fff; }
        .badge.research { background: #1f6feb; color: #fff; }
        .badge.conversation { background: #0f3460; color: #fff; }
        .badge.experience { background: #bf8700; color: #fff; }
        .badge.decision { background: #6e40c9; color: #fff; }

        .delete-btn {
            background: none; border: none; color: #888; cursor: pointer; font-size: 16px;
            padding: 2px 6px; border-radius: 4px; flex-shrink: 0;
        }
        .delete-btn:hover { color: #e94560; background: rgba(233,69,96,0.1); }

        #load-more { display: block; margin: 16px auto; }

        /* Toast */
        .toast {
            position: fixed; top: 20px; right: 20px; background: #e94560; color: #fff;
            padding: 12px 20px; border-radius: 8px; font-size: 14px; z-index: 999;
            opacity: 0; transform: translateY(-10px); transition: all 0.3s ease;
            max-width: 400px;
        }
        .toast.show { opacity: 1; transform: translateY(0); }
        .toast.success { background: #238636; }

        /* 状态图标 */
        .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; }
        .status-dot.sent { background: #238636; }
        .status-dot.pending { background: #bf8700; }
        .status-dot.failed { background: #e94560; }

        /* 图谱 */
        #graph-canvas { width: 100%; height: 400px; border: 1px solid #0f3460; border-radius: 8px; }

        /* 进度条 */
        .prog-bar { height: 6px; background: #1a1a2e; border-radius: 3px; overflow: hidden; margin-top: 4px; }
        .prog-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
        .prog-fill.high { background: #238636; }
        .prog-fill.mid { background: #bf8700; }
        .prog-fill.low { background: #0f3460; }

        /* 聊天 */
        #chat-messages { display: flex; flex-direction: column; gap: 12px; margin-bottom: 16px; }
        .msg { max-width: 80%; padding: 10px 14px; border-radius: 10px; line-height: 1.6; white-space: pre-wrap; font-size: 14px; }
        .msg.user { align-self: flex-end; background: #0f3460; }
        .msg.assistant { align-self: flex-start; background: #16213e; border: 1px solid #0f3460; }
        #input-area { display: flex; gap: 10px; }
        #message { flex: 1; padding: 10px 14px; border-radius: 8px; border: 1px solid #0f3460; background: #1a1a2e; color: #e0e0e0; resize: none; font-size: 14px; font-family: inherit; }
        #send { padding: 10px 22px; border: none; border-radius: 8px; background: #e94560; color: #fff; cursor: pointer; font-weight: 600; font-size: 14px; }
        #send:hover { background: #d63851; }
        #send:disabled { opacity: 0.5; cursor: not-allowed; }
        .loading { color: #888; font-style: italic; }

        /* 邮件 iframe */
        .email-frame { width: 100%; height: 400px; border: 1px solid #0f3460; border-radius: 8px; background: #fff; }

        /* 确认对话框 */
        .modal-overlay {
            position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000;
            display: flex; align-items: center; justify-content: center;
        }
        .modal-box {
            background: #16213e; border: 1px solid #0f3460; border-radius: 10px;
            padding: 24px; max-width: 400px; width: 90%;
        }
        .modal-box h3 { margin-bottom: 12px; font-size: 16px; }
        .modal-box p { color: #aaa; font-size: 14px; margin-bottom: 20px; }
        .modal-box .modal-actions { display: flex; gap: 10px; justify-content: flex-end; }
    </style>
</head>
<body>
    <header>
        <button id="toggle-sidebar" title="展开/收起菜单">&#9776;</button>
        <h1>Evomentor <span class="current-tab" id="current-tab-label"></span></h1>
    </header>

    <div id="main-wrap">
        <nav id="sidebar">
            <button class="tab-btn active" data-tab="chat"><span class="icon">&#128172;</span>聊天</button>
            <button class="tab-btn" data-tab="reports"><span class="icon">&#128196;</span>报告</button>
            <button class="tab-btn" data-tab="emails"><span class="icon">&#9993;</span>邮件</button>
            <button class="tab-btn" data-tab="memories"><span class="icon">&#129504;</span>记忆</button>
            <button class="tab-btn" data-tab="graph"><span class="icon">&#128279;</span>图谱</button>
            <button class="tab-btn" data-tab="skills"><span class="icon">&#128736;</span>Skills</button>
        </nav>

        <main id="content">
            <!-- 聊天 Tab -->
            <div class="tab-panel active" id="panel-chat">
                <div id="chat-messages"></div>
                <div id="input-area">
                    <textarea id="message" rows="2" placeholder="输入你的问题... (Enter 发送, Shift+Enter 换行)"></textarea>
                    <button id="send" onclick="sendMessage()">发送</button>
                </div>
            </div>

            <!-- 报告 Tab -->
            <div class="tab-panel" id="panel-reports">
                <div class="toolbar">
                    <input type="text" id="report-search" placeholder="搜索报告...">
                    <select id="report-type-filter">
                        <option value="">全部类型</option>
                        <option value="github">GitHub 分析</option>
                        <option value="research">研究搜索</option>
                    </select>
                </div>
                <div id="report-list"></div>
                <button class="secondary" id="report-load-more" style="display:none">加载更多</button>
            </div>

            <!-- 邮件 Tab -->
            <div class="tab-panel" id="panel-emails">
                <div class="toolbar">
                    <span style="font-size:13px;color:#888;">状态：</span>
                    <button class="secondary status-filter active" data-status="">全部</button>
                    <button class="secondary status-filter" data-status="sent">已发送</button>
                    <button class="secondary status-filter" data-status="pending">待发</button>
                    <button class="secondary status-filter" data-status="failed">失败</button>
                    <button id="send-all-btn" style="margin-left:auto;">立即发送全部</button>
                </div>
                <div id="email-list"></div>
                <button class="secondary" id="email-load-more" style="display:none">加载更多</button>
            </div>

            <!-- 记忆 Tab -->
            <div class="tab-panel" id="panel-memories">
                <div class="toolbar">
                    <input type="text" id="memory-search" placeholder="搜索记忆...">
                    <select id="memory-type-filter">
                        <option value="">全部类型</option>
                        <option value="conversation">对话</option>
                        <option value="experience">经验</option>
                        <option value="decision">决策</option>
                    </select>
                </div>
                <div id="memory-list"></div>
                <button class="secondary" id="memory-load-more" style="display:none">加载更多</button>
            </div>

            <!-- 知识图谱 Tab -->
            <div class="tab-panel" id="panel-graph">
                <canvas id="graph-canvas"></canvas>
                <div id="graph-legend" style="font-size:12px;color:#888;margin:8px 0;">
                    图例：深绿 = 掌握(5) &nbsp; 浅绿 = 熟练(3-4) &nbsp; 蓝色 = 了解(1-2)
                </div>
                <div id="graph-list"></div>
            </div>

            <!-- Skills Tab -->
            <div class="tab-panel" id="panel-skills">
                <div class="toolbar">
                    <input type="text" id="skill-search" placeholder="搜索 Skill...">
                </div>
                <div id="skill-list"></div>
                <button class="secondary" id="skill-load-more" style="display:none">加载更多</button>
            </div>
        </main>
    </div>

    <div class="toast" id="toast"></div>
    <div class="modal-overlay" id="modal" style="display:none;">
        <div class="modal-box">
            <h3>确认删除</h3>
            <p id="modal-msg">确定要删除这条记录吗？此操作不可撤销。</p>
            <div class="modal-actions">
                <button class="secondary" id="modal-cancel">取消</button>
                <button id="modal-confirm">确认删除</button>
            </div>
        </div>
    </div>

<script>
// ═══ 全局状态 ═══
const STATE = {
    sidebarOpen: false,
    currentTab: 'chat',
    reports: { offset: 0, items: [], hasMore: true },
    emails: { offset: 0, items: [], hasMore: true, status: '' },
    memories: { offset: 0, items: [], hasMore: true, type: '', search: '' },
    skills: { offset: 0, items: [], hasMore: true },
};

// ═══ 工具函数 ═══
function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

function showToast(msg, ok = false) {
    const t = $('#toast');
    t.textContent = msg; t.className = 'toast ' + (ok ? 'success' : '') + ' show';
    setTimeout(() => { t.classList.remove('show'); }, 2500);
}

function showModal(msg) {
    return new Promise(resolve => {
        $('#modal-msg').textContent = msg;
        $('#modal').style.display = 'flex';
        $('#modal-cancel').onclick = () => { $('#modal').style.display = 'none'; resolve(false); };
        $('#modal-confirm').onclick = () => { $('#modal').style.display = 'none'; resolve(true); };
    });
}

async function api(url, opts = {}) {
    try {
        const resp = await fetch(url, opts);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || `HTTP ${resp.status}`);
        }
        return await resp.json();
    } catch (e) {
        showToast('请求失败: ' + e.message);
        throw e;
    }
}

function simpleMd(text) {
    if (!text) return '';
    let html = text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/^### (.+)$/gm, '<h4>$1</h4>')
        .replace(/^## (.+)$/gm, '<h3>$1</h3>')
        .replace(/^# (.+)$/gm, '<h2>$1</h2>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/(?<!!)\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" style="color:#58a6ff;">$1</a>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/\n/g, '<br>');
    html = html.replace(/(<br>\s*)+/g, '<br>');
    return html;
}

function timeAgo(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr + (dateStr.endsWith('Z') ? '' : 'Z'));
    if (isNaN(d.getTime())) return dateStr;
    const now = new Date();
    const mins = Math.floor((now - d) / 60000);
    if (mins < 1) return '刚刚';
    if (mins < 60) return mins + '分钟前';
    const hours = Math.floor(mins / 60);
    if (hours < 24) return hours + '小时前';
    const days = Math.floor(hours / 24);
    if (days < 30) return days + '天前';
    return d.toLocaleDateString('zh-CN');
}

// ═══ 侧边栏 ═══
function toggleSidebar() {
    STATE.sidebarOpen = !STATE.sidebarOpen;
    $('#sidebar').classList.toggle('open', STATE.sidebarOpen);
}
$('#toggle-sidebar').addEventListener('click', toggleSidebar);

function switchTab(name) {
    STATE.currentTab = name;
    $$('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
    $$('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'panel-' + name));
    $('#current-tab-label').textContent = '— ' + {
        chat:'聊天', reports:'报告', emails:'邮件', memories:'记忆', graph:'图谱', skills:'Skills'
    }[name] || '';
    if (name === 'reports' && STATE.reports.items.length === 0) loadReports();
    if (name === 'emails' && STATE.emails.items.length === 0) loadEmails();
    if (name === 'memories' && STATE.memories.items.length === 0) loadMemories();
    if (name === 'graph') loadGraph();
    if (name === 'skills' && STATE.skills.items.length === 0) loadSkills();
}

$$('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ═══ 确认对话框 ═══
// (showModal 已在工具函数中定义)
</script>
</body>
</html>
```

- [ ] **Step 2: 启动服务，确认页面骨架正常显示**

```bash
python run.py
```

浏览器打开 `http://localhost:8000`，确认侧边栏可展开/收起、Tab 可切换。

- [ ] **Step 3: 提交**

```bash
git add src/web/templates/index.html
git commit -m "feat: 前端页面骨架 —— 侧边栏导航 + 6 个 Tab 面板

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: 前端 — 聊天 Tab 功能

**Files:**
- Modify: `src/web/templates/index.html`

**说明：** 在已有 JS 区域追加聊天相关逻辑，对标旧版功能。

- [ ] **Step 1: 在 `</script>` 前（即上文 `// ═══ 确认对话框 ═══` 注释之后）追加聊天逻辑**

```javascript
// ═══ 聊天 Tab ═══
const chatMessages = document.getElementById('chat-messages');
const msgInput = document.getElementById('message');
const sendBtn = document.getElementById('send');

msgInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

async function sendMessage() {
    const text = msgInput.value.trim();
    if (!text) return;
    addChatMsg('user', text);
    msgInput.value = '';
    sendBtn.disabled = true;
    const loading = addChatMsg('assistant', '思考中...', true);
    try {
        const data = await api('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
        });
        loading.remove();
        addChatMsg('assistant', data.reply);
    } catch (e) {
        loading.remove();
        addChatMsg('assistant', '出错了: ' + e.message);
    }
    sendBtn.disabled = false;
}

function addChatMsg(role, content, isLoading = false) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    div.textContent = content;
    if (isLoading) div.classList.add('loading');
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}
```

- [ ] **Step 2: 启动服务，测试聊天功能**

浏览器中切换到聊天 Tab，发送消息确认回复正常。

- [ ] **Step 3: 提交**

```bash
git add src/web/templates/index.html
git commit -m "feat: 聊天 Tab 功能 —— 发送消息与气泡展示

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 9: 前端 — 报告 Tab 功能

**Files:**
- Modify: `src/web/templates/index.html`

- [ ] **Step 1: 在 `</script>` 前追加报告 Tab 逻辑**

```javascript
// ═══ 报告 Tab ═══
async function loadReports(reset = true) {
    if (reset) { STATE.reports.offset = 0; STATE.reports.items = []; STATE.reports.hasMore = true; $('#report-list').innerHTML = ''; }
    if (!STATE.reports.hasMore) return;
    const type = $('#report-type-filter').value;
    const params = new URLSearchParams({ limit: '20', offset: String(STATE.reports.offset) });
    if (type) params.set('type', type);
    const data = await api('/api/reports?' + params);
    STATE.reports.items = STATE.reports.items.concat(data.items);
    STATE.reports.offset += data.items.length;
    STATE.reports.hasMore = data.items.length === 20;
    renderReportList();
    $('#report-load-more').style.display = STATE.reports.hasMore ? 'block' : 'none';
}

function renderReportList() {
    const container = $('#report-list');
    const search = ($('#report-search').value || '').toLowerCase();
    container.innerHTML = '';
    STATE.reports.items.forEach(item => {
        if (search && !item.title.toLowerCase().includes(search) && !item.preview.toLowerCase().includes(search)) return;
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <div class="card-header">
                <div>
                    <span class="badge ${item.type}">${item.type === 'github' ? 'GitHub' : '研究'}</span>
                    <span class="card-title">${escapeHtml(item.title)}</span>
                    <div class="card-meta">${timeAgo(item.created_at)}</div>
                </div>
                <button class="delete-btn" data-action="delete-report" data-id="${item.id}">&times;</button>
            </div>
            <div class="card-preview">${escapeHtml(item.preview)}</div>
            <div class="card-detail"></div>
        `;
        card.addEventListener('click', async (e) => {
            if (e.target.closest('[data-action]')) return;
            const detail = card.querySelector('.card-detail');
            if (card.classList.contains('expanded')) {
                card.classList.remove('expanded');
                return;
            }
            if (!detail.innerHTML) {
                detail.innerHTML = '<span style="color:#888;">加载中...</span>';
                try {
                    const full = await api('/api/reports/' + item.id);
                    detail.innerHTML = simpleMd(full.content || full.suggestions || '');
                } catch (e) {
                    detail.innerHTML = '<span style="color:#e94560;">加载失败</span>';
                }
            }
            card.classList.add('expanded');
        });
        container.appendChild(card);
    });
}

$('#report-search').addEventListener('input', () => renderReportList());
$('#report-type-filter').addEventListener('change', () => loadReports(true));
$('#report-load-more').addEventListener('click', () => loadReports(false));

// 委托删除事件
document.addEventListener('click', async (e) => {
    const del = e.target.closest('[data-action="delete-report"]');
    if (!del) return;
    e.stopPropagation();
    const id = del.dataset.id;
    if (!(await showModal('确定要删除这条报告吗？'))) return;
    await api('/api/reports/' + id, { method: 'DELETE' });
    STATE.reports.items = STATE.reports.items.filter(i => i.id !== id);
    renderReportList();
    showToast('已删除', true);
});
```

需要在工具函数区域追加 `escapeHtml`：

```javascript
function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}
```

- [ ] **Step 2: 启动服务，测试报告 Tab**

切换到报告 Tab，确认列表加载、点击展开详情、搜索筛选、删除功能正常。

- [ ] **Step 3: 提交**

```bash
git add src/web/templates/index.html
git commit -m "feat: 报告 Tab —— 列表、详情展开、搜索筛选、删除

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 10: 前端 — 邮件 Tab 功能

**Files:**
- Modify: `src/web/templates/index.html`

- [ ] **Step 1: 在 `</script>` 前追加邮件 Tab 逻辑**

```javascript
// ═══ 邮件 Tab ═══
async function loadEmails(reset = true) {
    if (reset) { STATE.emails.offset = 0; STATE.emails.items = []; STATE.emails.hasMore = true; $('#email-list').innerHTML = ''; }
    if (!STATE.emails.hasMore) return;
    const params = new URLSearchParams({ limit: '20', offset: String(STATE.emails.offset) });
    if (STATE.emails.status) params.set('status', STATE.emails.status);
    const data = await api('/api/emails?' + params);
    STATE.emails.items = STATE.emails.items.concat(data.items);
    STATE.emails.offset += data.items.length;
    STATE.emails.hasMore = data.items.length === 20;
    renderEmailList();
    $('#email-load-more').style.display = STATE.emails.hasMore ? 'block' : 'none';
}

function renderEmailList() {
    const container = $('#email-list');
    container.innerHTML = '';
    STATE.emails.items.forEach(item => {
        const statusText = { sent: '已发送', pending: '待发', failed: '失败' }[item.status] || item.status;
        const statusIcon = { sent: '&#9989;', pending: '&#9203;', failed: '&#10060;' }[item.status] || '';
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <div class="card-header">
                <div>
                    <span class="status-dot ${item.status}"></span>
                    <span style="font-size:12px;color:#888;">${statusIcon} ${statusText}</span>
                    <span class="card-title">${escapeHtml(item.subject || '(无主题)')}</span>
                    <div class="card-meta">${timeAgo(item.sent_at || item.scheduled_at)}</div>
                </div>
                <button class="delete-btn" data-action="delete-email" data-id="${item.id}">&times;</button>
            </div>
            <div class="card-preview">${escapeHtml(item.preview)}</div>
            <div class="card-detail"></div>
        `;
        card.addEventListener('click', async (e) => {
            if (e.target.closest('[data-action]')) return;
            const detail = card.querySelector('.card-detail');
            if (card.classList.contains('expanded')) { card.classList.remove('expanded'); return; }
            if (!detail.innerHTML) {
                detail.innerHTML = '<span style="color:#888;">加载中...</span>';
                try {
                    const full = await api('/api/emails/' + item.id);
                    detail.innerHTML = `<iframe class="email-frame" srcdoc="${full.body.replace(/"/g, '&quot;')}" sandbox="allow-same-origin"></iframe>`;
                } catch (e) {
                    detail.innerHTML = '<span style="color:#e94560;">加载失败</span>';
                }
            }
            card.classList.add('expanded');
        });
        container.appendChild(card);
    });
}

$$('.status-filter').forEach(btn => {
    btn.addEventListener('click', () => {
        $$('.status-filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        STATE.emails.status = btn.dataset.status;
        loadEmails(true);
    });
});

$('#send-all-btn').addEventListener('click', async () => {
    $('#send-all-btn').disabled = true;
    $('#send-all-btn').textContent = '发送中...';
    try {
        const data = await api('/api/emails/send', { method: 'POST' });
        showToast(data.result || '发送成功', true);
        loadEmails(true);
    } catch (e) {
        // 错误已在 api() 中提示
    }
    $('#send-all-btn').disabled = false;
    $('#send-all-btn').textContent = '立即发送全部';
});

$('#email-load-more').addEventListener('click', () => loadEmails(false));

document.addEventListener('click', async (e) => {
    const del = e.target.closest('[data-action="delete-email"]');
    if (!del) return;
    e.stopPropagation();
    const id = del.dataset.id;
    if (!(await showModal('确定要删除这封邮件吗？'))) return;
    await api('/api/emails/' + id, { method: 'DELETE' });
    STATE.emails.items = STATE.emails.items.filter(i => i.id !== Number(id));
    renderEmailList();
    showToast('已删除', true);
});
```

- [ ] **Step 2: 测试邮件 Tab**

切换到邮件 Tab，确认状态筛选、展开查看 HTML 内容、删除功能正常。

- [ ] **Step 3: 提交**

```bash
git add src/web/templates/index.html
git commit -m "feat: 邮件 Tab —— 状态筛选、展开 HTML、删除、手动发送

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 11: 前端 — 记忆 Tab 功能

**Files:**
- Modify: `src/web/templates/index.html`

- [ ] **Step 1: 在 `</script>` 前追加记忆 Tab 逻辑**

```javascript
// ═══ 记忆 Tab ═══
async function loadMemories(reset = true) {
    if (reset) { STATE.memories.offset = 0; STATE.memories.items = []; STATE.memories.hasMore = true; $('#memory-list').innerHTML = ''; }
    if (!STATE.memories.hasMore) return;
    const params = new URLSearchParams({ limit: '20', offset: String(STATE.memories.offset) });
    if (STATE.memories.type) params.set('type', STATE.memories.type);
    if (STATE.memories.search) params.set('search', STATE.memories.search);
    const data = await api('/api/memories?' + params);
    STATE.memories.items = STATE.memories.items.concat(data.items);
    STATE.memories.offset += data.items.length;
    STATE.memories.hasMore = data.items.length === 20;
    renderMemoryList();
    $('#memory-load-more').style.display = STATE.memories.hasMore ? 'block' : 'none';
}

function renderMemoryList() {
    const container = $('#memory-list');
    container.innerHTML = '';
    STATE.memories.items.forEach(item => {
        const typeLabel = { conversation: '对话', experience: '经验', decision: '决策' }[item.type] || item.type;
        const icon = { conversation: '&#128172;', experience: '&#128161;', decision: '&#129504;' }[item.type] || '';
        const card = document.createElement('div');
        card.className = 'card';
        let metaExtra = '';
        if (item.type === 'conversation') metaExtra = `角色: ${item.role} | 标签: ${item.tags}`;
        if (item.type === 'experience') metaExtra = `分类: ${item.category} | 来源: ${item.source} | 置信度: ${item.confidence}`;
        if (item.type === 'decision') metaExtra = `触发: ${item.trigger_name} | 工具: ${item.tool_calls}`;
        card.innerHTML = `
            <div class="card-header">
                <div>
                    <span class="badge ${item.type}">${icon} ${typeLabel}</span>
                    <span class="card-title">${escapeHtml(item.title)}</span>
                    <div class="card-meta">${timeAgo(item.created_at)} &nbsp; ${escapeHtml(metaExtra)}</div>
                </div>
                <button class="delete-btn" data-action="delete-memory" data-id="${item.id}">&times;</button>
            </div>
            <div class="card-preview">${escapeHtml(item.preview)}</div>
            <div class="card-detail">${simpleMd(item.outcome || item.preview || '')}</div>
        `;
        card.addEventListener('click', (e) => {
            if (e.target.closest('[data-action]')) return;
            card.classList.toggle('expanded');
        });
        container.appendChild(card);
    });
}

$('#memory-search').addEventListener('input', () => {
    STATE.memories.search = $('#memory-search').value;
    loadMemories(true);
});
$('#memory-type-filter').addEventListener('change', () => {
    STATE.memories.type = $('#memory-type-filter').value;
    loadMemories(true);
});
$('#memory-load-more').addEventListener('click', () => loadMemories(false));

document.addEventListener('click', async (e) => {
    const del = e.target.closest('[data-action="delete-memory"]');
    if (!del) return;
    e.stopPropagation();
    const id = del.dataset.id;
    if (!(await showModal('确定要删除这条记忆吗？'))) return;
    await api('/api/memories/' + id, { method: 'DELETE' });
    STATE.memories.items = STATE.memories.items.filter(i => i.id !== id);
    renderMemoryList();
    showToast('已删除', true);
});
```

- [ ] **Step 2: 测试记忆 Tab**

切换到记忆 Tab，确认类型筛选、搜索、展开详情、删除功能正常。

- [ ] **Step 3: 提交**

```bash
git add src/web/templates/index.html
git commit -m "feat: 记忆 Tab —— 类型筛选、搜索、展开、删除

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 12: 前端 — 知识图谱 Tab 功能

**Files:**
- Modify: `src/web/templates/index.html`

- [ ] **Step 1: 在 `</script>` 前追加知识图谱 Tab 逻辑**

```javascript
// ═══ 知识图谱 Tab ═══
async function loadGraph() {
    const data = await api('/api/graph');
    drawGraph(data.nodes, data.edges);
    renderGraphList(data.nodes);
}

function drawGraph(nodes, edges) {
    const canvas = $('#graph-canvas');
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = 400 * dpr;
    ctx.scale(dpr, dpr);
    canvas.style.width = rect.width + 'px';
    canvas.style.height = '400px';

    const w = rect.width;
    const h = 400;
    ctx.clearRect(0, 0, w, h);

    if (nodes.length === 0) {
        ctx.fillStyle = '#888';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('暂无知识图谱数据', w / 2, h / 2);
        return;
    }

    // 简单圆形布局
    const cx = w / 2, cy = h / 2;
    const radius = Math.min(w, h) / 2 - 60;
    const nodePositions = {};

    nodes.forEach((node, i) => {
        const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
        const x = cx + radius * Math.cos(angle);
        const y = cy + radius * Math.sin(angle);
        nodePositions[node.id] = { x, y };
    });

    // 绘制边
    edges.forEach(edge => {
        const from = nodePositions[edge.from];
        const to = nodePositions[edge.to];
        if (!from || !to) return;
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
        ctx.strokeStyle = '#0f3460';
        ctx.lineWidth = 1.5;
        ctx.stroke();
    });

    // 绘制节点
    nodes.forEach(node => {
        const pos = nodePositions[node.id];
        if (!pos) return;
        const size = 12 + node.proficiency * 4;
        const colors = ['#0f3460', '#1f6feb', '#bf8700', '#238636', '#238636', '#238636'];
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, size, 0, 2 * Math.PI);
        ctx.fillStyle = colors[Math.min(node.proficiency, 5)] || '#0f3460';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.fillStyle = '#e0e0e0';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(node.label, pos.x, pos.y + size + 14);
    });
}

function renderGraphList(nodes) {
    const container = $('#graph-list');
    container.innerHTML = '<h3 style="margin:16px 0 10px;">知识点列表</h3>';
    nodes.forEach(node => {
        const div = document.createElement('div');
        div.className = 'card';
        const levelText = node.proficiency >= 5 ? '掌握' : node.proficiency >= 3 ? '熟练' : '了解';
        const levelClass = node.proficiency >= 5 ? 'high' : node.proficiency >= 3 ? 'mid' : 'low';
        div.innerHTML = `
            <div class="card-header">
                <span class="card-title">${escapeHtml(node.label)}</span>
                <span style="font-size:12px;color:#888;">${levelText} (${node.proficiency}/5)</span>
            </div>
            <div class="prog-bar"><div class="prog-fill ${levelClass}" style="width:${node.proficiency * 20}%"></div></div>
        `;
        container.appendChild(div);
    });
}

window.addEventListener('resize', () => {
    if (STATE.currentTab === 'graph') loadGraph();
});
```

- [ ] **Step 2: 测试知识图谱 Tab**

切换到图谱 Tab，确认 Canvas 图渲染正确、知识点列表显示进度条。

- [ ] **Step 3: 提交**

```bash
git add src/web/templates/index.html
git commit -m "feat: 知识图谱 Tab —— Canvas 关系图 + 知识点进度列表

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 13: 前端 — Skills Tab 功能

**Files:**
- Modify: `src/web/templates/index.html`

- [ ] **Step 1: 在 `</script>` 前追加 Skills Tab 逻辑**

```javascript
// ═══ Skills Tab ═══
async function loadSkills(reset = true) {
    if (reset) { STATE.skills.offset = 0; STATE.skills.items = []; STATE.skills.hasMore = true; $('#skill-list').innerHTML = ''; }
    if (!STATE.skills.hasMore) return;
    const params = new URLSearchParams({ limit: '20', offset: String(STATE.skills.offset) });
    const data = await api('/api/skills?' + params);
    STATE.skills.items = STATE.skills.items.concat(data.items);
    STATE.skills.offset += data.items.length;
    STATE.skills.hasMore = data.items.length === 20;
    renderSkillList();
    $('#skill-load-more').style.display = STATE.skills.hasMore ? 'block' : 'none';
}

function renderSkillList() {
    const container = $('#skill-list');
    const search = ($('#skill-search').value || '').toLowerCase();
    container.innerHTML = '';
    STATE.skills.items.forEach(item => {
        if (search && !item.name.toLowerCase().includes(search) && !item.trigger_condition.toLowerCase().includes(search)) return;
        const activeLabel = item.active ? '活跃' : '闲置';
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <div class="card-header">
                <div>
                    <span style="font-size:16px;">&#128736;</span>
                    <span class="card-title">${escapeHtml(item.name)}</span>
                    <span style="font-size:11px;color:#888;">v${item.version} · ${activeLabel}</span>
                    <div class="card-meta">触发: ${escapeHtml(item.trigger_condition || '')}</div>
                    <div class="card-meta">使用: ${item.usage_count}次 · 成功率: ${(item.success_rate * 100).toFixed(0)}%</div>
                </div>
                <button class="delete-btn" data-action="delete-skill" data-id="${item.id}">&times;</button>
            </div>
            <div class="card-detail"></div>
        `;
        card.addEventListener('click', async (e) => {
            if (e.target.closest('[data-action]')) return;
            const detail = card.querySelector('.card-detail');
            if (card.classList.contains('expanded')) { card.classList.remove('expanded'); return; }
            if (!detail.innerHTML) {
                detail.innerHTML = '<span style="color:#888;">加载中...</span>';
                try {
                    const full = await api('/api/skills/' + item.id);
                    detail.innerHTML = simpleMd(full.file_content || full.behavior_rules || '暂无内容');
                } catch (e) {
                    detail.innerHTML = '<span style="color:#e94560;">加载失败</span>';
                }
            }
            card.classList.add('expanded');
        });
        container.appendChild(card);
    });
}

$('#skill-search').addEventListener('input', () => renderSkillList());
$('#skill-load-more').addEventListener('click', () => loadSkills(false));

document.addEventListener('click', async (e) => {
    const del = e.target.closest('[data-action="delete-skill"]');
    if (!del) return;
    e.stopPropagation();
    const id = del.dataset.id;
    if (!(await showModal('确定要删除这个 Skill 吗？将同时删除对应的 .md 文件。'))) return;
    await api('/api/skills/' + id, { method: 'DELETE' });
    STATE.skills.items = STATE.skills.items.filter(i => i.id !== Number(id));
    renderSkillList();
    showToast('已删除', true);
});
```

- [ ] **Step 2: 测试 Skills Tab**

切换到 Skills Tab，确认列表加载、搜索筛选、展开查看 Markdown 内容、删除功能正常。

- [ ] **Step 3: 提交**

```bash
git add src/web/templates/index.html
git commit -m "feat: Skills Tab —— 列表、详情展开、搜索、删除

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 14: API — 反思触发按钮接入前端

**Files:**
- Modify: `src/web/templates/index.html`

- [ ] **Step 1: 在报告 Tab 的 toolbar 中增加反思按钮**

找到 `<!-- 报告 Tab -->` 区域的 toolbar div，在其中追加：

```html
<button id="trigger-reflect-btn" style="margin-left:auto;">手动反思</button>
```

- [ ] **Step 2: 在 JS 区域追加反思触发逻辑**

```javascript
// ═══ 反思触发 ═══
$('#trigger-reflect-btn').addEventListener('click', async () => {
    const btn = $('#trigger-reflect-btn');
    btn.disabled = true;
    btn.textContent = '反思中...';
    try {
        const data = await api('/api/reflect', { method: 'POST' });
        showToast(data.result || '反思完成', true);
        // 刷新报告和记忆列表
        loadReports(true);
    } catch (e) {
        // 错误已在 api() 中提示
    }
    btn.disabled = false;
    btn.textContent = '手动反思';
});
```

- [ ] **Step 2: 测试反思触发**

在报告 Tab 点击"手动反思"按钮，确认返回结果并在页面显示 toast。

- [ ] **Step 3: 提交**

```bash
git add src/web/templates/index.html
git commit -m "feat: 前端接入手动反思触发按钮

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 15: 集成验证

**Files:** 无新建，验证全部功能。

- [ ] **Step 1: 启动服务**

```bash
python run.py
```

- [ ] **Step 2: 逐 Tab 验收**

| Tab | 验证项 |
|-----|--------|
| 聊天 | 发送消息 → 收到回复，气泡正常 |
| 报告 | 列表加载 → 搜索筛选 → 展开详情 → 删除 |
| 邮件 | 状态筛选 → 展开 HTML → 删除 |
| 记忆 | 类型筛选 → 搜索 → 展开 → 删除 |
| 图谱 | Canvas 渲染 → 节点/边显示 → 知识点列表 |
| Skills | 列表加载 → 展开 Markdown → 删除 |
| 全局 | 侧边栏展开/收起 → Toast → 确认弹窗 |

- [ ] **Step 3: 运行已有测试确保无回归**

```bash
pytest tests/ -v
```

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "chore: 集成验证通过，前端仪表盘实现完成

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## 总结

- **新增 API 端点：** 10 个（报告 3 + 邮件 4 + 记忆 2 + 图谱 1 + Skills 3 + 反思 1，含 chat 原有共计 12 个端点）
- **前端 Tab：** 6 个（聊天 / 报告 / 邮件 / 记忆 / 图谱 / Skills）
- **零新依赖：** 全部使用 Python 标准库 + Vanilla JS + Canvas API
- **预计改动行数：** routes.py +~250 行，index.html 完全重写 ~650 行
