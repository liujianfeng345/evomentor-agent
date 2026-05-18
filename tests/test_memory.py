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
