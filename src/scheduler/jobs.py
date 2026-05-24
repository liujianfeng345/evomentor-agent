"""定时任务 —— 基于用户活跃度智能触发。"""
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.core.agent import Agent
from src.core.config import config
from src.core.logger import get_logger
from src.memory.long_term import lts
from src.db.connection import get_connection
from src.research.manager import ResearchManager

scheduler = AsyncIOScheduler()
agent = Agent()
research_logger = get_logger("research")


def _last_activity() -> datetime:
    """获取用户最后一次活跃时间。"""
    conn = get_connection()
    row = conn.execute(
        "SELECT created_at FROM conversations WHERE role = 'user' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        return datetime.fromisoformat(row["created_at"])
    return datetime.min


async def periodic_check() -> None:
    """周期性检查：仅在用户空闲时触发。"""
    last = _last_activity()
    idle_hours = (datetime.now() - last).total_seconds() / 3600

    if idle_hours >= config.IDLE_HOURS_BEFORE_TRIGGER:
        await agent.handle_scheduled("periodic_check")


async def daily_reflect() -> None:
    """每日反思：每天凌晨触发一次。"""
    await agent.handle_scheduled("reflect")


async def send_daily_email() -> None:
    """每日邮件：每天只发一封，合并所有待发内容。"""
    # 检查今天是否已发送
    conn = get_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM pending_emails WHERE status = 'sent' AND date(sent_at) = ?",
        (today,),
    ).fetchone()
    conn.close()

    if row and row["cnt"] > 0:
        return  # 今天已发过

    await agent.handle_scheduled("periodic_check")


async def scheduled_research() -> None:
    """定时研究任务：为所有活跃主题生成研究报告并发送邮件。"""
    manager = ResearchManager()
    reports = await manager.run_all()
    if reports:
        # 所有主题报告已入邮件队列，触发发送
        from src.tools.email_tool import EmailTool
        email_tool = EmailTool()
        result = await email_tool.execute()
        research_logger.info(
            "[SCHEDULED] 研究完成: %d 篇报告, 邮件: %s",
            len(reports), result.content,
        )


def start_scheduler() -> None:
    """启动调度器。"""
    # 每 30 分钟检查一次用户活跃度
    scheduler.add_job(
        periodic_check,
        IntervalTrigger(minutes=30),
        id="periodic_check",
        name="周期性检查",
        replace_existing=True,
    )
    # 每天反思（间隔24小时）
    scheduler.add_job(
        daily_reflect,
        IntervalTrigger(hours=24),
        id="daily_reflect",
        name="每日反思",
        replace_existing=True,
    )
    # 每天定时研究报告（间隔24小时）
    scheduler.add_job(
        scheduled_research,
        IntervalTrigger(hours=config.RESEARCH_SCHEDULE_HOURS),
        id="scheduled_research",
        name="定时研究报告",
        replace_existing=True,
    )
    scheduler.start()
