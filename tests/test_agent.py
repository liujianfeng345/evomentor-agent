import pytest
from src.core.agent import Agent


@pytest.mark.asyncio
async def test_agent_chat():
    agent = Agent()
    response = await agent.handle_message("你好")
    assert response
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_agent_scheduled():
    agent = Agent()
    response = await agent.handle_scheduled("reflect")
    assert response
    assert isinstance(response, str)
