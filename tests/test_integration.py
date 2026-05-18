"""集成测试 —— 端到端验证核心流程。"""
import pytest
from src.core.agent import Agent


@pytest.mark.asyncio
async def test_full_chat_flow():
    """测试完整对话流程：发送消息 → 获得回复 → 对话被持久化。"""
    agent = Agent()
    reply = await agent.handle_message("我在学习 Python 异步编程，有什么建议？")
    assert reply
    assert isinstance(reply, str)
    assert len(reply) > 0


@pytest.mark.asyncio
async def test_reflect_flow():
    """测试反思流程。"""
    agent = Agent()
    # 先模拟一些对话
    await agent.handle_message("什么是 asyncio？")
    await agent.handle_message("如何用 aiohttp 发请求？")
    # 执行反思
    reply = await agent.handle_scheduled("reflect")
    assert reply
    assert isinstance(reply, str)


@pytest.mark.asyncio
async def test_memory_persistence():
    """测试记忆持久化：对话保存后能从数据库读取。"""
    from src.memory.long_term import lts
    agent = Agent()
    await agent.handle_message("测试记忆持久化")
    conversations = lts.get_conversations_by_session(agent.session_id)
    assert len(conversations) > 0
