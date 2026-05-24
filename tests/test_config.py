"""配置模块单元测试。"""
import pytest
from src.core.config import Config


class TestConfig:
    def test_default_values(self):
        cfg = Config()
        assert cfg.SHORT_TERM_MAX_MESSAGES == 50
        assert cfg.LLM_MAX_RETRIES == 3
        assert cfg.DEEPSEEK_BASE_URL == "https://api.deepseek.com"
        assert cfg.SKILL_CONFIDENCE_THRESHOLD == 0.5

    def test_available_models_structure(self):
        cfg = Config()
        for m in cfg.AVAILABLE_MODELS:
            assert "id" in m
            assert "name" in m
            assert "provider" in m
            assert "model" in m
            assert "base_url" in m

    def test_default_model_in_available(self):
        cfg = Config()
        model_ids = [m["id"] for m in cfg.AVAILABLE_MODELS]
        assert cfg.DEFAULT_MODEL in model_ids

    def test_embedding_provider_default(self):
        cfg = Config()
        assert cfg.EMBEDDING_PROVIDER == "chromadb"
