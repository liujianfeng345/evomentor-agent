"""测试流式聊天端点和 SSE 事件格式。"""
import json
import pytest
from httpx import AsyncClient, ASGITransport
from src.web.app import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_chat_stream_endpoint_exists():
    """验证流式端点已注册。"""
    from src.web.routes import router
    paths = [r.path for r in router.routes]
    assert "/api/chat/stream" in paths


@pytest.mark.asyncio
async def test_chat_stream_returns_sse_events(client):
    """验证流式端点返回 SSE 格式的 text/event-stream。"""
    async with client.stream(
        "POST", "/api/chat/stream",
        json={"message": "你好"},
        timeout=60.0,
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        # 读取至少一个事件
        events = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                events.append(data)
            if len(events) >= 5:  # 最多读 5 个事件后停止
                break

        assert len(events) > 0
        # 验证事件结构
        assert "type" in events[0]


@pytest.mark.asyncio
async def test_non_streaming_chat_still_works(client):
    """验证原有非流式端点不受影响。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(
            "/api/chat",
            json={"message": "你好"},
            timeout=60.0,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
