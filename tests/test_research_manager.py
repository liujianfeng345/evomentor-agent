# tests/test_research_manager.py
"""ResearchManager 单元测试。"""
import pytest
from src.research.manager import ResearchManager, _slugify, DEPTH_ROUNDS


class TestSlugify:
    def test_slugify_chinese(self):
        assert _slugify("LLM Agent 最新进展") == "LLM_Agent_最新进展"

    def test_slugify_special_chars(self):
        result = _slugify("a/b:c?d*e")
        assert "/" not in result
        assert ":" not in result
        assert "?" not in result
        assert "*" not in result

    def test_slugify_long_name(self):
        long_name = "A" * 100
        result = _slugify(long_name)
        assert len(result) <= 60


class TestDepthRounds:
    def test_depth_config(self):
        assert DEPTH_ROUNDS["quick"] == 1
        assert DEPTH_ROUNDS["standard"] == 2
        assert DEPTH_ROUNDS["deep"] == 3


class TestResearchManagerInit:
    def test_init(self):
        manager = ResearchManager()
        assert manager.research_tool is not None
        assert manager.web_search_tool is not None

    def test_get_topics_empty(self):
        manager = ResearchManager()
        topics = manager._get_topics()
        assert isinstance(topics, list)

    def test_get_topic_not_found(self):
        manager = ResearchManager()
        result = manager._get_topic_by_id(99999)
        assert result is None
