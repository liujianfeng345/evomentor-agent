"""日志模块单元测试。"""
import os
import sys
import pytest


class TestTruncate:
    """测试截断工具函数。"""

    def test_short_text_unchanged(self):
        """短文本不截断。"""
        from src.core.logger import truncate
        assert truncate("hello", max_len=10) == "hello"

    def test_exact_length_unchanged(self):
        """恰好等于长度限制不截断。"""
        from src.core.logger import truncate
        assert truncate("1234567890", max_len=10) == "1234567890"

    def test_long_text_truncated(self):
        """超长文本截断并加标记。"""
        from src.core.logger import truncate
        result = truncate("123456789012345", max_len=10)
        assert result == "1234567890...[截断]"
        assert len(result) <= 10 + len("...[截断]")

    def test_custom_max_len(self):
        """自定义截断长度。"""
        from src.core.logger import truncate
        result = truncate("abcdefghijklmnop", max_len=5)
        assert result == "abcde...[截断]"

    def test_empty_string(self):
        """空字符串不报错。"""
        from src.core.logger import truncate
        assert truncate("", max_len=10) == ""

    def test_chinese_text(self):
        """中文文本也可正确截断。"""
        from src.core.logger import truncate
        result = truncate("你好世界这是一个很长的文本用来测试截断功能", max_len=10)
        assert result.endswith("...[截断]")


class TestGetLogger:
    """测试日志获取函数。"""

    def test_returns_logger(self):
        """get_logger 返回 Logger 实例。"""
        from src.core.logger import get_logger
        import logging
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_same_name_same_logger(self):
        """同一名称返回同一 logger 实例。"""
        from src.core.logger import get_logger
        logger1 = get_logger("test_same")
        logger2 = get_logger("test_same")
        assert logger1 is logger2
