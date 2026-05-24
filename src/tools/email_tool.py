"""邮件工具 —— 合并待发内容，润色后通过 SMTP 发送。"""
from src.tools.base import BaseTool, ToolResult
from datetime import datetime
from src.core.git_auto import record_generation
import os
from src.core.config import config
from src.core.llm import llm
from src.db.models import get_connection
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class EmailTool(BaseTool):
    name = "send_email"
    description = "合并待发邮件内容，经 LLM 润色后发送给用户。"

    async def execute(self, to_email: str = "") -> ToolResult:
        if not config.SMTP_USER:
            return ToolResult(success=False, content="SMTP 未配置")

        to = to_email or config.SMTP_USER

        # 1. 从队列中拉取待发内容
        conn = get_connection()
        pending = conn.execute(
            "SELECT * FROM pending_emails WHERE status = 'pending' ORDER BY scheduled_at"
        ).fetchall()
        conn.close()

        if not pending:
            # 队列为空时，从 agent_reports 表取最新报告作为 fallback
            conn = get_connection()
            row = conn.execute(
                "SELECT title, content FROM agent_reports ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if not row:
                return ToolResult(success=True, content="没有待发送的邮件，也无可用报告。")
            # 构造虚拟 pending 列表用于后续流程
            pending = [{"subject": row["title"], "body": row["content"], "id": None}]

        # 2. 合并内容并润色
        parts = [f"## {p['subject']}\n{p['body']}" for p in pending]
        raw = "\n\n---\n\n".join(parts)

        polish_prompt = f"""请将以下内容润色为一封友好的学习周报邮件，使用 HTML 格式：

原始内容:
{raw}

要求：
- 开头有亲切的问候
- 总结近期学习重点
- 列出代码改进建议
- 推荐前沿方向和资源
- 结尾鼓励用户
- 纯 HTML，适合邮件客户端阅读"""

        response = llm.chat([{"role": "user", "content": polish_prompt}])

        # 保存报告到本地文件
        os.makedirs("reports", exist_ok=True)
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M%S")
        report_path = f"reports/weekly-report-{date_str}-{time_str}.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(response["content"])
        record_generation(report_path, f"生成学习周报 {date_str}")

        # 3. 发送邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Evomentor 学习周报 — {datetime.now().strftime('%Y-%m-%d')}"
        msg["From"] = config.SMTP_USER
        msg["To"] = to
        msg.attach(MIMEText(response["content"], "html", "utf-8"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=config.SMTP_HOST,
                port=config.SMTP_PORT,
                username=config.SMTP_USER,
                password=config.SMTP_PASSWORD,
                start_tls=True,
            )
        except Exception as e:
            # 标记为失败（仅更新有 id 的记录，fallback 记录无 id 无需标记）
            conn = get_connection()
            for p in pending:
                if p.get("id") is not None:
                    conn.execute(
                        "UPDATE pending_emails SET status = 'failed' WHERE id = ?", (p["id"],)
                    )
            conn.commit()
            conn.close()
            return ToolResult(success=False, content=f"邮件发送失败: {e}")

        # 4. 标记为已发送
        conn = get_connection()
        has_fallback = False
        for p in pending:
            if p.get("id") is not None:
                conn.execute(
                    "UPDATE pending_emails SET status = 'sent', sent_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (p["id"],),
                )
            else:
                has_fallback = True
        # fallback 发送成功后插入一条 sent 记录，确保防重复检查能正确计数
        if has_fallback:
            conn.execute(
                "INSERT INTO pending_emails (subject, body, status, sent_at) VALUES (?, ?, 'sent', CURRENT_TIMESTAMP)",
                (pending[0]["subject"], pending[0]["body"]),
            )
        conn.commit()
        conn.close()

        return ToolResult(success=True, content=f"已发送 {len(pending)} 封邮件到 {to}")

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "to_email": {"type": "string", "description": "收件人邮箱，默认使用配置中的 SMTP_USER"},
            },
        }
