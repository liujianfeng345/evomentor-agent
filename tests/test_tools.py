import pytest
from src.memory.short_term import ShortTermMemory


@pytest.mark.asyncio
async def test_chat_tool():
    from src.tools.chat import ChatTool
    mem = ShortTermMemory()
    tool = ChatTool(mem)
    result = await tool.execute("什么是 Python 装饰器？")
    assert result.success
    assert result.content
    assert len(mem.get_all()) == 2  # user + assistant
