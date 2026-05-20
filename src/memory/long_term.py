"""长期记忆 —— 通过 SQLite 持久化经验、Skill、偏好、知识图谱。"""
import json
from src.db.models import get_connection


class LongTermMemory:
    # --- 经验 ---
    def save_experience(self, category: str, title: str, content: str,
                        source: str = "", confidence: float = 0.5) -> int:
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO experiences (category, title, content, source, confidence) VALUES (?, ?, ?, ?, ?)",
            (category, title, content, source, confidence),
        )
        conn.commit()
        exp_id = cursor.lastrowid
        conn.close()
        return exp_id

    def get_experiences_by_category(self, category: str, limit: int = 10) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM experiences WHERE category = ? ORDER BY created_at DESC LIMIT ?",
            (category, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def update_experience_confidence(self, exp_id: int, delta: float) -> None:
        conn = get_connection()
        conn.execute(
            "UPDATE experiences SET confidence = MIN(1.0, MAX(0.0, confidence + ?)) WHERE id = ?",
            (delta, exp_id),
        )
        conn.commit()
        conn.close()

    # --- 偏好 ---
    def save_preference(self, key: str, value: str) -> None:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO user_knowledge_graph (topic, proficiency, parent_topic) VALUES (?, 5, 'preference')",
            (f"{key}:{value}",),
        )
        conn.commit()
        conn.close()

    def get_preferences(self) -> dict[str, str]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT topic FROM user_knowledge_graph WHERE parent_topic = 'preference'"
        ).fetchall()
        conn.close()
        prefs = {}
        for row in rows:
            if ":" in row["topic"]:
                k, v = row["topic"].split(":", 1)
                prefs[k] = v
        return prefs

    # --- 知识图谱 ---
    def update_knowledge(self, topic: str, proficiency: int, parent: str = "") -> None:
        conn = get_connection()
        existing = conn.execute(
            "SELECT id, proficiency FROM user_knowledge_graph WHERE topic = ? AND parent_topic != 'preference'",
            (topic,),
        ).fetchone()
        if existing:
            new_prof = max(existing["proficiency"], proficiency)
            conn.execute(
                "UPDATE user_knowledge_graph SET proficiency = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
                (new_prof, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO user_knowledge_graph (topic, proficiency, parent_topic) VALUES (?, ?, ?)",
                (topic, proficiency, parent),
            )
        conn.commit()
        conn.close()

    def get_knowledge_graph(self) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM user_knowledge_graph WHERE parent_topic != 'preference' ORDER BY proficiency DESC"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- 决策日志 ---
    def log_decision(self, trigger: str, tool_calls: list, reasoning: str, outcome: str) -> int:
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO agent_decisions (trigger, tool_calls, reasoning, outcome) VALUES (?, ?, ?, ?)",
            (trigger, json.dumps(tool_calls, ensure_ascii=False), reasoning, outcome),
        )
        conn.commit()
        dec_id = cursor.lastrowid
        conn.close()
        return dec_id

    def get_recent_decisions(self, limit: int = 20) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM agent_decisions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # --- 对话 ---
    def save_conversation(self, role: str, content: str, tags: list[str],
                          intent: str, session_id: str) -> int:
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO conversations (role, content, topic_tags, intent, session_id) VALUES (?, ?, ?, ?, ?)",
            (role, content, json.dumps(tags, ensure_ascii=False), intent, session_id),
        )
        conn.commit()
        conv_id = cursor.lastrowid
        conn.close()
        return conv_id

    def get_conversations_by_session(self, session_id: str, limit: int = 50) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM conversations WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    def save_agent_report(self, trigger: str, title: str, content: str, session_id: str) -> int:
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO agent_reports (trigger, title, content, session_id) VALUES (?, ?, ?, ?)",
            (trigger, title, content, session_id),
        )
        conn.commit()
        report_id = cursor.lastrowid
        conn.close()
        return report_id


lts = LongTermMemory()
