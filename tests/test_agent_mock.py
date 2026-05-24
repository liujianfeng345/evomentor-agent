"""Agent 循环 mock 测试 —— 不依赖真实 LLM API。"""
import pytest
from unittest.mock import AsyncMock, patch
from src.core.agent import Agent
from src.tools.base import ToolResult


class TestAgentWithMockLLM:
    @pytest.mark.asyncio
    async def test_agent_direct_reply_without_tools(self):
        """LLM 返回无 tool_calls 的回复时，Agent 直接结束。"""
        agent = Agent()
        with patch("src.core.agent.retrieve_relevant_context", return_value=""):
            with patch("src.core.agent.llm.chat") as mock_chat:
                mock_chat.return_value = {"content": "你好！有什么可以帮你的？", "role": "assistant"}
                with patch("src.core.agent.lts"):
                    with patch("src.core.agent.commit_and_push", return_value=""):
                        response = await agent.handle_message("你好")
                        assert "你好" in response

    @pytest.mark.asyncio
    async def test_agent_with_tool_calls(self):
        """LLM 返回 tool_calls 时，Agent 执行 tool 后继续。"""
        agent = Agent()
        with patch("src.core.agent.retrieve_relevant_context", return_value=""):
            with patch("src.core.agent.llm.chat") as mock_chat:
                mock_chat.side_effect = [
                    {
                        "content": "",
                        "role": "assistant",
                        "tool_calls": [{
                            "id": "call_1",
                            "name": "chat",
                            "arguments": {"message": "hello", "session_id": "test"},
                        }],
                    },
                    {"content": "回复完毕", "role": "assistant"},
                ]
                # Mock 工具执行，避免真实 LLM 调用
                mock_tool = AsyncMock()
                mock_tool.execute.return_value = ToolResult(success=True, content="工具执行成功")
                with patch.object(agent.tools, "get", return_value=mock_tool):
                    with patch("src.core.agent.lts"):
                        with patch("src.core.agent.commit_and_push", return_value=""):
                            response = await agent.handle_message("帮我聊天")
                            assert "回复完毕" in response

    @pytest.mark.asyncio
    async def test_agent_tool_failure_continues_loop(self):
        """Tool 执行失败时，Agent 不中断循环。"""
        agent = Agent()
        with patch("src.core.agent.retrieve_relevant_context", return_value=""):
            with patch("src.core.agent.llm.chat") as mock_chat:
                mock_chat.side_effect = [
                    {
                        "content": "",
                        "role": "assistant",
                        "tool_calls": [{
                            "id": "call_1",
                            "name": "chat",
                            "arguments": {"message": "test"},
                        }],
                    },
                    {"content": "虽然工具失败了，但我可以继续", "role": "assistant"},
                ]
                mock_tool = AsyncMock()
                mock_tool.execute.side_effect = Exception("模拟失败")
                with patch.object(agent.tools, "get", return_value=mock_tool):
                    with patch("src.core.agent.lts"):
                        with patch("src.core.agent.commit_and_push", return_value=""):
                            response = await agent.handle_message("test")
                            assert response  # 不应抛出异常
