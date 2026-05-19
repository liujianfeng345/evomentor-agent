"""API 路由 —— Web 聊天接口。"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
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


class ChatResponse(BaseModel):
    reply: str


class DeleteResponse(BaseModel):
    ok: bool


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    agent = get_agent()
    reply = await agent.handle_message(req.message)
    return ChatResponse(reply=reply)


@router.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


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
