"""测试操作面板 API 端点。"""
import json
import pytest
from httpx import AsyncClient, ASGITransport
from src.web.app import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_actions_endpoint_returns_list(client):
    """验证 GET /api/actions 返回正确的操作列表。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert "actions" in data
        assert len(data["actions"]) == 3
        triggers = [a["trigger"] for a in data["actions"]]
        assert "periodic_check" in triggers
        assert "reflect" in triggers
        assert "send_email" in triggers
        for a in data["actions"]:
            assert "trigger" in a
            assert "name" in a
            assert "description" in a
            assert "icon" in a


@pytest.mark.asyncio
async def test_actions_stream_endpoint_registered():
    """验证 POST /api/actions/stream 路由已注册。"""
    from src.web.routes import router
    paths = [r.path for r in router.routes]
    assert "/api/actions/stream" in paths


@pytest.mark.asyncio
async def test_actions_stream_invalid_trigger(client):
    """验证无效 trigger 返回 400 错误。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/actions/stream",
            json={"trigger": "invalid_trigger"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data


@pytest.mark.asyncio
async def test_actions_stream_returns_sse(client):
    """验证有效 trigger 返回 SSE text/event-stream。"""
    async with client.stream(
        "POST", "/api/actions/stream",
        json={"trigger": "reflect"},
        timeout=60.0,
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        events = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                events.append(data)
            if len(events) >= 5:
                break

        assert len(events) > 0
        assert "type" in events[0]


@pytest.mark.asyncio
async def test_actions_list_matches_constant():
    """验证 API 返回的 actions 与后端 ACTIONS 常量一致。"""
    from src.web.routes import ACTIONS
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["actions"] == ACTIONS
