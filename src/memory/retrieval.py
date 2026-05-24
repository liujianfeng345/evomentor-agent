"""记忆检索 —— 关键词匹配 + 语义检索，在 Agent 感知阶段使用。"""
from src.db.vector_store import vector_store
from src.memory.long_term import lts
from src.db.connection import get_connection


def retrieve_relevant_context(query: str, top_k: int = 5) -> str:
    """根据当前查询，从长期记忆和向量库中检索相关上下文。"""
    parts = []

    # 1. 关键词匹配 —— 从 SQLite 查相关经验
    keywords = _extract_keywords(query)
    for kw in keywords:
        exps = lts.get_experiences_by_category("code_pattern", limit=3)
        for exp in exps:
            if kw.lower() in exp["title"].lower() or kw.lower() in exp["content"].lower():
                parts.append(f"[经验] {exp['title']}: {exp['content'][:200]}")

    # 2. 语义检索 —— 从 ChromaDB 搜索
    results = vector_store.search("experience_embeddings", query, n_results=top_k)
    for r in results:
        parts.append(f"[相关记忆] {r['document'][:300]}")

    # 3. 加载用户知识图谱
    graph = lts.get_knowledge_graph()
    if graph:
        parts.append("[知识图谱] " + ", ".join(
            f"{g['topic']}(Lv{g['proficiency']})" for g in graph[:10]
        ))

    # 4. 加载活跃 Skills
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, trigger_condition FROM skills WHERE active = 1"
    ).fetchall()
    conn.close()
    if rows:
        parts.append("[活跃 Skills] " + "; ".join(
            f"{r['name']}: {r['trigger_condition']}" for r in rows
        ))

    return "\n".join(parts)


def _extract_keywords(text: str) -> list[str]:
    """简单提取关键词（后续可升级为 NLP 分词）。"""
    # 去标点，取长度 > 2 的词
    import re
    words = re.findall(r"[\w一-鿿]{2,}", text)
    return list(set(words))[:10]
