"""短期记忆单元测试。"""
import pytest
from src.memory.short_term import ShortTermMemory, Message


class TestMessage:
    def test_message_to_dict_basic(self):
        msg = Message(role="user", content="hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "hello"
        assert "timestamp" in d

    def test_message_to_dict_with_tool_calls(self):
        msg = Message(role="assistant", content="",
                      tool_calls=[{"id": "1", "type": "function", "function": {"name": "test", "arguments": "{}"}}])
        d = msg.to_dict()
        assert "tool_calls" in d
        assert d["tool_calls"][0]["id"] == "1"

    def test_message_to_dict_with_tool_call_id(self):
        msg = Message(role="tool", content="result", tool_call_id="call_123")
        d = msg.to_dict()
        assert d["tool_call_id"] == "call_123"


class TestShortTermMemory:
    def test_add_message(self):
        mem = ShortTermMemory()
        mem.add("user", "hello")
        assert len(mem.get_all()) == 1

    def test_trim_when_exceeds_max(self):
        mem = ShortTermMemory()
        for i in range(60):
            mem.add("user", f"msg {i}")
        assert len(mem.get_all()) <= 50

    def test_clear(self):
        mem = ShortTermMemory()
        mem.add("user", "hello")
        mem.clear()
        assert len(mem.get_all()) == 0

    def test_add_assistant_tool_calls(self):
        mem = ShortTermMemory()
        mem.add_assistant_tool_calls(
            content="",
            tool_calls_schema=[{"id": "1", "type": "function", "function": {"name": "t", "arguments": "{}"}}],
        )
        msgs = mem.get_all()
        assert msgs[0].role == "assistant"
        assert msgs[0].tool_calls is not None

    def test_add_tool_result(self):
        mem = ShortTermMemory()
        mem.add_tool_result("test_tool", "done", tool_call_id="1")
        msgs = mem.get_all()
        assert msgs[0].role == "tool"
        assert "done" in msgs[0].content

    def test_get_for_llm_basic(self):
        mem = ShortTermMemory()
        mem.add("user", "hello")
        msgs = mem.get_for_llm()
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "hello"

    def test_get_for_llm_with_tool(self):
        mem = ShortTermMemory()
        mem.add_assistant_tool_calls("", [{"id": "1", "type": "function", "function": {"name": "t", "arguments": "{}"}}])
        mem.add_tool_result("test_tool", "result", tool_call_id="1")
        msgs = mem.get_for_llm()
        assert msgs[0]["tool_calls"] is not None
        assert msgs[1]["tool_call_id"] == "1"

    def test_is_full(self):
        mem = ShortTermMemory()
        assert not mem.is_full()
        for i in range(60):
            mem.add("user", f"msg {i}")
        assert mem.is_full()

    def test_summarize_for_compression(self):
        mem = ShortTermMemory()
        mem.add("user", "hello world")
        mem.add("assistant", "hi there")
        result = mem.summarize_for_compression()
        assert "[user]" in result
        assert "[assistant]" in result

    def test_reasoning_content_preserved(self):
        mem = ShortTermMemory()
        mem.add_assistant_tool_calls(
            content="thinking...", tool_calls_schema=[],
            reasoning_content="deep reasoning here",
        )
        msgs = mem.get_for_llm()
        assert msgs[0].get("reasoning_content") == "deep reasoning here"
