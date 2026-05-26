"""测试 /api/graph 端点的增强功能。"""
import pytest
from fastapi.testclient import TestClient
from src.web.routes import router
from src.db.models import init_db
from src.db.connection import get_connection

client = TestClient(router)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    conn = get_connection()
    # 清理旧数据
    conn.execute("DELETE FROM user_knowledge_graph")
    # 插入测试数据
    conn.execute(
        "INSERT INTO user_knowledge_graph (topic, proficiency, parent_topic) VALUES (?, ?, ?)",
        ("Python 装饰器", 3, "Python 生态"),
    )
    conn.execute(
        "INSERT INTO user_knowledge_graph (topic, proficiency, parent_topic) VALUES (?, ?, ?)",
        ("asyncio 异步", 2, "Python 生态"),
    )
    conn.execute(
        "INSERT INTO user_knowledge_graph (topic, proficiency, parent_topic) VALUES (?, ?, ?)",
        ("Transformer 架构", 4, "人工智能"),
    )
    conn.execute(
        "INSERT INTO user_knowledge_graph (topic, proficiency, parent_topic) VALUES (?, ?, ?)",
        ("偏好设置", 5, "preference"),
    )
    conn.commit()
    conn.close()
    yield
    # 清理
    conn = get_connection()
    conn.execute("DELETE FROM user_knowledge_graph")
    conn.commit()
    conn.close()


def test_graph_returns_groups_field():
    """响应应包含 groups 列表。"""
    resp = client.get("/api/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "groups" in data
    assert isinstance(data["groups"], list)
    assert "Python 生态" in data["groups"]
    assert "人工智能" in data["groups"]
    assert "preference" not in data["groups"]


def test_graph_nodes_have_group_field():
    """每个节点应有 group 字段。"""
    resp = client.get("/api/graph")
    data = resp.json()
    for node in data["nodes"]:
        assert "group" in node
        assert "id" in node
        assert "label" in node
        assert "proficiency" in node


def test_graph_excludes_preference():
    """parent_topic 为 preference 的行不出现在节点中。"""
    resp = client.get("/api/graph")
    data = resp.json()
    labels = [n["label"] for n in data["nodes"]]
    assert "偏好设置" not in labels


def test_graph_search_filter():
    """search 参数模糊匹配 topic。"""
    resp = client.get("/api/graph?search=装饰器")
    data = resp.json()
    # 排除 is_category 虚拟锚点节点，只检查真实节点
    real_nodes = [n for n in data["nodes"] if not n.get("is_category")]
    assert len(real_nodes) == 1
    assert real_nodes[0]["label"] == "Python 装饰器"


def test_graph_parent_filter():
    """parent 参数按 parent_topic 筛选。"""
    resp = client.get("/api/graph?parent=Python 生态")
    data = resp.json()
    labels = [n["label"] for n in data["nodes"]]
    assert "Python 装饰器" in labels
    assert "asyncio 异步" in labels
    assert "Transformer 架构" not in labels


def test_graph_min_level_filter():
    """min_level 参数过滤熟练度低于阈值的节点。"""
    resp = client.get("/api/graph?min_level=3")
    data = resp.json()
    # 排除 is_category 虚拟锚点节点（其 proficiency 总是 0）
    real_nodes = [n for n in data["nodes"] if not n.get("is_category")]
    for node in real_nodes:
        assert node["proficiency"] >= 3


def test_graph_no_ghost_nodes_with_negative_ids():
    """不应出现负数 ID 的幽灵节点。"""
    resp = client.get("/api/graph")
    data = resp.json()
    for node in data["nodes"]:
        assert node["id"] > 0


def test_graph_combined_filters():
    """组合筛选：parent + min_level + search。"""
    resp = client.get("/api/graph?parent=Python 生态&min_level=2&search=asyncio")
    data = resp.json()
    # 排除 is_category 虚拟锚点节点，只检查真实节点
    real_nodes = [n for n in data["nodes"] if not n.get("is_category")]
    assert len(real_nodes) == 1
    assert real_nodes[0]["label"] == "asyncio 异步"
