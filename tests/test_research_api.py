# tests/test_research_api.py
"""研究 API 端点测试。"""
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.web.routes import router
from src.db.models import init_db


@pytest.fixture
def client():
    """创建测试客户端，确保数据库已初始化。"""
    init_db()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestResearchTopicsAPI:
    """主题 CRUD 接口测试。"""

    def test_list_topics(self, client):
        """获取主题列表。"""
        response = client.get("/api/research/topics")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_create_topic(self, client):
        """创建主题。"""
        response = client.post(
            "/api/research/topics",
            json={"name": "测试主题", "description": "测试描述", "depth": "standard"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["topic"]["name"] == "测试主题"
        assert data["topic"]["depth"] == "standard"
        topic_id = data["topic"]["id"]

        # 清理
        client.delete(f"/api/research/topics/{topic_id}")

    def test_create_duplicate_topic(self, client):
        """创建重复主题应返回 409。"""
        response = client.post(
            "/api/research/topics",
            json={"name": "重复测试主题", "depth": "standard"},
        )
        assert response.status_code == 200
        topic_id = response.json()["topic"]["id"]

        response = client.post(
            "/api/research/topics",
            json={"name": "重复测试主题", "depth": "standard"},
        )
        assert response.status_code == 409

        client.delete(f"/api/research/topics/{topic_id}")

    def test_update_topic(self, client):
        """修改主题。"""
        response = client.post(
            "/api/research/topics",
            json={"name": "更新测试主题", "depth": "quick"},
        )
        topic_id = response.json()["topic"]["id"]

        response = client.put(
            f"/api/research/topics/{topic_id}",
            json={"depth": "deep", "status": "paused"},
        )
        assert response.status_code == 200
        assert response.json()["topic"]["depth"] == "deep"
        assert response.json()["topic"]["status"] == "paused"

        client.delete(f"/api/research/topics/{topic_id}")

    def test_delete_topic(self, client):
        """删除主题。"""
        response = client.post(
            "/api/research/topics",
            json={"name": "删除测试主题", "depth": "quick"},
        )
        topic_id = response.json()["topic"]["id"]

        response = client.delete(f"/api/research/topics/{topic_id}")
        assert response.status_code == 200
        assert response.json()["ok"] is True

        response = client.delete(f"/api/research/topics/{topic_id}")
        assert response.status_code == 404

    def test_list_research_reports(self, client):
        """研究报告列表端点。"""
        response = client.get("/api/research/reports")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
