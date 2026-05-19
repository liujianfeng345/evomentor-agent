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


@pytest.mark.asyncio
async def test_static_css_served(client):
    """验证静态 CSS 文件可访问。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/static/style.css")
        assert resp.status_code == 200
        assert "text/css" in resp.headers.get("content-type", "")
        assert len(resp.text) > 1000


@pytest.mark.asyncio
async def test_index_page_loads(client):
    """验证主页 HTML 可加载且引用外部 CSS。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/")
        assert resp.status_code == 200
        html = resp.text
        assert '/static/style.css' in html
        assert '<style>' not in html


@pytest.mark.asyncio
async def test_models_endpoint_returns_list(client):
    """验证 /api/models 返回模型列表且不含敏感信息。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "default" in data
        assert len(data["models"]) >= 1
        for m in data["models"]:
            assert "id" in m
            assert "name" in m
            assert "provider" in m
            assert "icon" in m
            assert "api_key" not in m


@pytest.mark.asyncio
async def test_chat_stream_supports_model_param(client):
    """验证流式端点接受 model 参数并正常响应。"""
    async with client.stream(
        "POST", "/api/chat/stream",
        json={"message": "你好", "model": "deepseek-v4-flash"},
        timeout=60.0,
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        events = []
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
            if len(events) >= 2:
                break
        assert len(events) > 0


@pytest.mark.asyncio
async def test_chat_stream_invalid_model_falls_back(client):
    """验证无效 model ID 回退到默认模型，不报错。"""
    async with client.stream(
        "POST", "/api/chat/stream",
        json={"message": "你好", "model": "nonexistent-model"},
        timeout=60.0,
    ) as resp:
        assert resp.status_code == 200


def test_web_search_tool_schema():
    """验证 web_search 工具的 LLM Schema 正确。"""
    from src.tools.web_search import WebSearchTool
    tool = WebSearchTool()
    schema = tool.to_llm_schema()
    assert schema["function"]["name"] == "web_search"
    params = schema["function"]["parameters"]
    assert "query" in params["properties"]
    assert params["required"] == ["query"]
    assert "search_depth" in params["properties"]
    assert set(params["properties"]["search_depth"]["enum"]) == {"basic", "advanced"}


@pytest.mark.asyncio
async def test_web_search_execute_handles_no_api_key():
    """验证 web_search 无 API key 时不抛异常，返回错误信息。"""
    from src.tools.web_search import WebSearchTool
    tool = WebSearchTool()
    result = await tool.execute(query="test", search_depth="basic")
    assert result is not None
    assert hasattr(result, "content")
