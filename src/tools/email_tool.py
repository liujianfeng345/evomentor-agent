"""邮件工具 —— 合并待发内容，润色后通过 SMTP 发送。"""
from src.tools.base import BaseTool, ToolResult
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
            return ToolResult(success=True, content="没有待发送的邮件。")

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

        # 3. 发送邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Evomentor 学习周报 — {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}"
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
            # 标记为失败
            conn = get_connection()
            for p in pending:
                conn.execute(
                    "UPDATE pending_emails SET status = 'failed' WHERE id = ?", (p["id"],)
                )
            conn.commit()
            conn.close()
            return ToolResult(success=False, content=f"邮件发送失败: {e}")

        # 4. 标记为已发送
        conn = get_connection()
        for p in pending:
            conn.execute(
                "UPDATE pending_emails SET status = 'sent', sent_at = CURRENT_TIMESTAMP WHERE id = ?",
                (p["id"],),
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
