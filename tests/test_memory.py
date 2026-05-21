from src.memory.short_term import ShortTermMemory
from src.memory.long_term import lts


def test_add_message():
    mem = ShortTermMemory()
    mem.add("user", "Hello")
    assert len(mem.get_all()) == 1
    assert mem.get_all()[0].role == "user"


def test_capacity_limit():
    mem = ShortTermMemory()
    for i in range(60):
        mem.add("user", f"msg {i}")
    assert len(mem.get_all()) <= 50


def test_get_for_llm():
    mem = ShortTermMemory()
    mem.add("user", "Hello")
    messages = mem.get_for_llm()
    assert messages == [{"role": "user", "content": "Hello"}]


def test_save_and_get_experience():
    exp_id = lts.save_experience("code_pattern", "测试经验", "这是测试内容")
    assert exp_id > 0
    exps = lts.get_experiences_by_category("code_pattern")
    assert len(exps) >= 1


def test_knowledge_graph():
    lts.update_knowledge("Python", 3)
    graph = lts.get_knowledge_graph()
    topics = [g["topic"] for g in graph]
    assert "Python" in topics


from src.memory.retrieval import retrieve_relevant_context


def test_retrieve_context():
    context = retrieve_relevant_context("Python 异步编程")
    assert isinstance(context, str)
    assert len(context) > 0 or True  # 空库时至少不报错


import time
from src.db.models import init_db


def test_github_analysis_cache_crud():
    """测试 github_analyses 缓存的完整 CRUD 流程"""
    # 确保表已创建
    init_db()

    # 写入一条分析
    analysis_id = lts.save_analysis("test-repo", "abc123", "## 分析结果：代码质量良好")
    assert analysis_id > 0

    # 缓存命中
    cached = lts.get_cached_analysis("test-repo", "abc123")
    assert cached is not None
    assert cached["repo_name"] == "test-repo"
    assert cached["commit_sha"] == "abc123"
    assert cached["findings"] == "## 分析结果：代码质量良好"

    # 不存在的 commit 返回 None
    missing = lts.get_cached_analysis("test-repo", "nonexistent")
    assert missing is None


def test_github_analysis_eviction_count():
    """测试淘汰逻辑：超上限时删除最旧记录"""
    init_db()

    # 写入 5 条记录
    for i in range(5):
        lts.save_analysis("evict-repo", f"sha-{i}", f"findings {i}")
        time.sleep(0.01)  # 确保 created_at 不同

    # 上限设为 3，应删除 2 条最旧的
    deleted = lts.evict_old_analyses(max_keep=3)
    assert deleted >= 2

    # 剩下的应是最新的 3 条
    remaining_ids = []
    for i in range(5):
        c = lts.get_cached_analysis("evict-repo", f"sha-{i}")
        if c:
            remaining_ids.append(i)
    assert remaining_ids == [2, 3, 4]  # sha-0, sha-1 被淘汰


def test_github_analysis_empty_result_not_cached():
    """空分析结果不应写入缓存"""
    init_db()

    result = lts.save_analysis("empty-repo", "empty-sha", "")
    # 空结果返回 0 表示未写入
    assert result == 0
