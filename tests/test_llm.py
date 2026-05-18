"""LLM 客户端测试。"""
import os
import pytest
from src.core.llm import llm


def test_chat_basic():
    """测试基本聊天功能——若有 API Key 则实际调用，否则跳过。"""
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("需要 API Key")
    result = llm.chat([{"role": "user", "content": "回复'测试通过'"}])
    assert result["content"]
    assert result["role"] == "assistant"
