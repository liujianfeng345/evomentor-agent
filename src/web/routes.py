"""API 路由 —— Web 聊天接口。"""
import json
import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from src.core.agent import Agent

router = APIRouter()

# 全局 Agent 实例（应用启动时初始化）
_agent: Agent | None = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


class ChatRequest(BaseModel):
    message: str
    model: str = ""  # 模型 ID，空则用默认


class ChatResponse(BaseModel):
    reply: str


class DeleteResponse(BaseModel):
    ok: bool


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    agent = get_agent()
    reply = await agent.handle_message(req.message, model_id=req.model)
    return ChatResponse(reply=reply)


@router.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/api/models")
async def list_models():
    """返回可用模型列表（不含 API key 等敏感信息）。"""
    from src.core.config import config as app_config
    return {
        "models": [
            {
                "id": m["id"],
                "name": m["name"],
                "provider": m["provider"],
                "icon": m.get("icon", ""),
                "description": m.get("description", ""),
            }
            for m in app_config.AVAILABLE_MODELS
        ],
        "default": app_config.DEFAULT_MODEL,
    }


@router.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式聊天 SSE 端点。"""
    agent = get_agent()

    async def event_generator():
        async for event in agent.handle_message_stream(req.message, model_id=req.model):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


"""报告与记忆相关的 API 端点。"""
from src.db.models import get_connection

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
    try:
        prefix, rid = parts[0], int(parts[1])
    except ValueError:
        conn.close()
        return JSONResponse({"error": "无效的报告 ID"}, status_code=400)

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
    try:
        prefix, rid = parts[0], int(parts[1])
    except ValueError:
        conn.close()
        return JSONResponse({"error": "无效的报告 ID"}, status_code=400)

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

    try:
        prefix, mid = parts[0], int(parts[1])
    except ValueError:
        conn.close()
        return JSONResponse({"error": "无效的记忆 ID"}, status_code=400)

    table_map = {"conv": "conversations", "exp": "experiences", "dec": "agent_decisions"}
    table = table_map.get(prefix)
    if not table:
        conn.close()
        return JSONResponse({"error": "未知记忆类型"}, status_code=400)
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (mid,))
    conn.commit()
    conn.close()
    return {"ok": True}

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
    missing_id = -1
    for edge in edges:
        if edge["from"] not in topic_ids:
            nodes.append({
                "id": missing_id,
                "label": edge["from"],
                "proficiency": 0,
            })
            topic_ids[edge["from"]] = missing_id
            missing_id -= 1

    # 将 edge 的 label 转为 id
    resolved_edges = []
    for edge in edges:
        from_id = topic_ids.get(edge["from"])
        to_id = topic_ids.get(edge["to"])
        if from_id is not None and to_id is not None:
            resolved_edges.append({"from": from_id, "to": to_id})

    return {"nodes": nodes, "edges": resolved_edges}

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
        try:
            os.remove(row["file_path"])
        except OSError:
            pass  # 文件删除失败不影响数据库记录清理
    conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
    conn.commit()
    conn.close()
    return {"ok": True}

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
