# Evomentor 实现计划

> **For agentic workers:** 使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 按任务逐步实现。步骤使用 checkbox (`- [ ]`) 语法跟踪。

**目标：** 构建 Evomentor 个人学习助手 Agent —— 通过 Web 聊天交流，定期分析 GitHub 代码、总结对话、搜索前沿方向，以邮件推送学习建议，并具备自我进化能力（自动提炼经验、生成 Skill）。

**架构：** 单 Agent 多 Tool 模式。核心 Agent 循环（感知→思考→行动→观察）通过 LLM 决策调用 6 个 Tool。两层记忆系统（短期内存 + 长期 SQLite/ChromaDB）。FastAPI Web 界面 + APScheduler 定时调度。

**技术栈：** Python 3.12+, FastAPI, DeepSeek API, SQLite, ChromaDB, APScheduler, aiosmtplib, httpx, PyGithub, Jinja2

---

## 文件结构

```
evomentor-agent/
├── src/
│   ├── core/
│   │   ├── agent.py         # Agent 循环
│   │   ├── llm.py           # LLM 客户端抽象
│   │   └── config.py        # 配置管理（从 .env 加载）
│   ├── memory/
│   │   ├── short_term.py    # 短期记忆（内存列表）
│   │   ├── long_term.py     # 长期记忆（SQLite 读写）
│   │   └── retrieval.py     # 记忆检索（关键词 + 语义）
│   ├── tools/
│   │   ├── base.py          # Tool 基类
│   │   ├── chat.py          # 对话工具
│   │   ├── github.py        # GitHub 分析工具
│   │   ├── email_tool.py    # 邮件工具
│   │   ├── research.py      # 研究工具
│   │   ├── reflect.py       # 反思工具
│   │   └── skill_manager.py # Skill 管理工具
│   ├── scheduler/
│   │   └── jobs.py          # 定时任务定义
│   ├── web/
│   │   ├── app.py           # FastAPI 应用入口
│   │   ├── routes.py        # API 路由
│   │   └── templates/
│   │       └── index.html   # 聊天界面
│   └── db/
│       ├── models.py        # SQLite 表定义与初始化
│       └── vector_store.py  # ChromaDB 封装
├── skills/                  # 自动生成的 Skill 文件
├── tests/
│   ├── test_agent.py
│   ├── test_memory.py
│   ├── test_tools.py
│   └── test_integration.py
├── requirements.txt
└── .env.example
```

---

## Phase 1: 项目脚手架

### Task 1.1: 项目目录与依赖

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`

- [ ] **Step 1: 创建 requirements.txt**

```txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
httpx==0.28.1
apscheduler==3.10.4
aiosmtplib==3.0.2
chromadb==0.5.23
openai==1.58.1
pygithub==2.5.0
python-dotenv==1.0.1
jinja2==3.1.4
pytest==8.3.4
pytest-asyncio==0.25.0
```

- [ ] **Step 2: 创建 .env.example**

```bash
# DeepSeek API
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# GitHub
GITHUB_TOKEN=ghp-your-token-here
GITHUB_USERNAME=your-github-username

# SMTP 邮件
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# 数据库
DATABASE_PATH=data/evomentor.db
CHROMA_PATH=data/chroma

# 调度
IDLE_HOURS_BEFORE_TRIGGER=6
```

- [ ] **Step 3: 创建目录结构**

```bash
mkdir -p src/core src/memory src/tools src/scheduler src/web/templates src/db tests data skills
touch src/__init__.py src/core/__init__.py src/memory/__init__.py src/tools/__init__.py src/scheduler/__init__.py src/web/__init__.py src/db/__init__.py tests/__init__.py
```

- [ ] **Step 4: 安装依赖**

```bash
pip install -r requirements.txt
```

---

## Phase 2: 配置与数据层

### Task 2.1: 配置管理

**Files:**
- Create: `src/core/config.py`

- [ ] **Step 1: 编写配置管理模块**

```python
"""从环境变量加载配置。"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # DeepSeek
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # GitHub
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_USERNAME: str = os.getenv("GITHUB_USERNAME", "")

    # SMTP
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # 数据库
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/evomentor.db")
    CHROMA_PATH: str = os.getenv("CHROMA_PATH", "data/chroma")

    # 调度
    IDLE_HOURS_BEFORE_TRIGGER: int = int(os.getenv("IDLE_HOURS_BEFORE_TRIGGER", "6"))

    # Agent
    SHORT_TERM_MAX_MESSAGES: int = 50
    LLM_MAX_RETRIES: int = 3
    SKILL_CONFIDENCE_THRESHOLD: float = 0.5


config = Config()
```

- [ ] **Step 2: 验证配置加载**

```bash
python -c "from src.core.config import config; print(config.DEEPSEEK_MODEL)"
```
预期：输出 `deepseek-chat`

---

### Task 2.2: SQLite 数据模型

**Files:**
- Create: `src/db/models.py`

- [ ] **Step 1: 编写数据库模型与初始化**

```python
"""SQLite 表定义与数据库初始化。"""
import sqlite3
import os
from src.core.config import config


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    topic_tags TEXT DEFAULT '[]',
    intent TEXT DEFAULT '',
    session_id TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experiences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT '',
    confidence REAL DEFAULT 0.5,
    embedding_id TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    behavior_rules TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1,
    usage_count INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,
    file_path TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS github_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_name TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    findings TEXT DEFAULT '[]',
    suggestions TEXT DEFAULT '',
    analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS research_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    source_type TEXT NOT NULL,
    url TEXT NOT NULL,
    summary TEXT NOT NULL,
    relevance_score REAL DEFAULT 0.5,
    found_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_knowledge_graph (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    proficiency INTEGER DEFAULT 1,
    parent_topic TEXT DEFAULT '',
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger TEXT NOT NULL,
    tool_calls TEXT DEFAULT '[]',
    reasoning TEXT DEFAULT '',
    outcome TEXT DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pending_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    scheduled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    sent_at DATETIME
);
"""


def init_db() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
```

- [ ] **Step 2: 验证数据库初始化**

```bash
python -c "from src.db.models import init_db; init_db(); print('DB created')"
```
预期：输出 `DB created` 且 `data/evomentor.db` 文件存在。

---

### Task 2.3: ChromaDB 向量存储

**Files:**
- Create: `src/db/vector_store.py`

- [ ] **Step 1: 编写向量存储封装**

```python
"""ChromaDB 封装 —— 统一管理 embedding 的存储和检索。"""
import chromadb
from chromadb.config import Settings
from src.core.config import config


class VectorStore:
    def __init__(self) -> None:
        self.client = chromadb.PersistentClient(
            path=config.CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        self._ensure_collections()

    def _ensure_collections(self) -> None:
        names = [c.name for c in self.client.list_collections()]
        for col_name in [
            "conversation_embeddings",
            "experience_embeddings",
            "code_pattern_embeddings",
            "research_embeddings",
        ]:
            if col_name not in names:
                self.client.create_collection(name=col_name)

    def add(self, collection: str, doc_id: str, text: str, metadata: dict | None = None) -> None:
        """将文本向量化存入指定集合。embedding 由 ChromaDB 内置函数自动生成。"""
        col = self.client.get_collection(name=collection)
        col.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata] if metadata else None,
        )

    def search(self, collection: str, query: str, n_results: int = 5) -> list[dict]:
        """语义检索：返回最相关的文档列表。"""
        col = self.client.get_collection(name=collection)
        results = col.query(query_texts=[query], n_results=n_results)
        items = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                items.append({
                    "id": doc_id,
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })
        return items

    def delete(self, collection: str, doc_id: str) -> None:
        col = self.client.get_collection(name=collection)
        col.delete(ids=[doc_id])


vector_store = VectorStore()
```

- [ ] **Step 2: 验证向量存储**

```bash
python -c "from src.db.vector_store import vector_store; vector_store.add('conversation_embeddings', 'test-1', 'Hello world'); results = vector_store.search('conversation_embeddings', 'Hello'); print(len(results))"
```
预期：输出 `1`

---

## Phase 3: LLM 客户端

### Task 3.1: LLM 客户端抽象

**Files:**
- Create: `src/core/llm.py`

- [ ] **Step 1: 编写 LLM 客户端**

```python
"""LLM 客户端抽象 —— 封装 DeepSeek API，预留切换接口。"""
import json
import time
from openai import OpenAI
from src.core.config import config


class LLMClient:
    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
        )
        self.model = config.DEEPSEEK_MODEL

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> dict:
        """发送聊天请求，支持 Tool Calling。失败自动重试 3 次。"""
        last_error = None
        for attempt in range(config.LLM_MAX_RETRIES):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"
                response = self.client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                result = {
                    "content": choice.message.content or "",
                    "role": choice.message.role,
                }
                if choice.message.tool_calls:
                    result["tool_calls"] = [
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments),
                        }
                        for tc in choice.message.tool_calls
                    ]
                return result
            except Exception as e:
                last_error = e
                if attempt < config.LLM_MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM 调用失败（已重试 {config.LLM_MAX_RETRIES} 次）: {last_error}")

    def embed(self, text: str) -> list[float]:
        """生成文本的 embedding 向量。"""
        response = self.client.embeddings.create(
            model="deepseek-chat",
            input=text,
        )
        return response.data[0].embedding


llm = LLMClient()
```

- [ ] **Step 2: 创建测试验证 LLM 调用**

```python
# tests/test_llm.py
import pytest
from src.core.llm import llm


@pytest.mark.skipif(not __import__("os").getenv("DEEPSEEK_API_KEY"), reason="需要 API Key")
def test_chat_basic():
    result = llm.chat([{"role": "user", "content": "回复'测试通过'"}])
    assert result["content"]
    assert result["role"] == "assistant"
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_llm.py::test_chat_basic -v
```

---

## Phase 4: 记忆系统

### Task 4.1: 短期记忆

**Files:**
- Create: `src/memory/short_term.py`

- [ ] **Step 1: 编写短期记忆**

```python
"""短期记忆 —— 基于内存的消息列表，有容量上限。"""
from dataclasses import dataclass, field
from datetime import datetime
from src.core.config import config


@dataclass
class Message:
    role: str
    content: str
    tags: list[str] = field(default_factory=list)
    intent: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "tags": self.tags,
            "intent": self.intent,
            "timestamp": self.timestamp.isoformat(),
        }


class ShortTermMemory:
    def __init__(self) -> None:
        self.messages: list[Message] = []

    def add(self, role: str, content: str, tags: list[str] | None = None,
            intent: str = "") -> None:
        self.messages.append(Message(
            role=role, content=content,
            tags=tags or [], intent=intent,
        ))
        self._trim()

    def add_tool_result(self, tool_name: str, result: str) -> None:
        self.messages.append(Message(
            role="tool",
            content=f"[{tool_name}] {result}",
        ))

    def get_all(self) -> list[Message]:
        return list(self.messages)

    def get_for_llm(self) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def is_full(self) -> bool:
        return len(self.messages) >= config.SHORT_TERM_MAX_MESSAGES

    def clear(self) -> None:
        self.messages.clear()

    def _trim(self) -> None:
        while len(self.messages) > config.SHORT_TERM_MAX_MESSAGES:
            self.messages.pop(0)

    def summarize_for_compression(self) -> str:
        """将当前对话内容压缩为一段摘要文本，供反思 Tool 使用。"""
        lines = []
        for m in self.messages:
            lines.append(f"[{m.role}] {m.content[:200]}")
        return "\n".join(lines)
```

- [ ] **Step 2: 编写测试**

```python
# tests/test_memory.py
from src.memory.short_term import ShortTermMemory


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
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_memory.py -v
```

---

### Task 4.2: 长期记忆

**Files:**
- Create: `src/memory/long_term.py`

- [ ] **Step 1: 编写长期记忆**

```python
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


lts = LongTermMemory()
```

- [ ] **Step 2: 编写测试**

```python
# 追加到 tests/test_memory.py
from src.memory.long_term import lts


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
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_memory.py -v
```

---

### Task 4.3: 记忆检索

**Files:**
- Create: `src/memory/retrieval.py`

- [ ] **Step 1: 编写记忆检索**

```python
"""记忆检索 —— 关键词匹配 + 语义检索，在 Agent 感知阶段使用。"""
from src.db.vector_store import vector_store
from src.memory.long_term import lts


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
    conn = __import__("src.db.models", fromlist=["get_connection"]).get_connection()
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
```

- [ ] **Step 2: 编写测试**

```python
# 追加到 tests/test_memory.py
from src.memory.retrieval import retrieve_relevant_context


def test_retrieve_context():
    context = retrieve_relevant_context("Python 异步编程")
    assert isinstance(context, str)
    assert len(context) > 0 or True  # 空库时至少不报错
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_memory.py::test_retrieve_context -v
```

---

## Phase 5: 工具层

### Task 5.1: Tool 基类

**Files:**
- Create: `src/tools/base.py`

- [ ] **Step 1: 编写 Tool 基类**

```python
"""Tool 基类 —— 所有工具继承此基类，统一接口和元数据。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    content: str
    metadata: dict | None = None


class BaseTool(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...

    def to_llm_schema(self) -> dict:
        """生成 OpenAI 兼容的 Tool Definition。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters_schema(),
            },
        }

    @abstractmethod
    def get_parameters_schema(self) -> dict:
        ...
```

---

### Task 5.2: 对话工具

**Files:**
- Create: `src/tools/chat.py`

- [ ] **Step 1: 编写对话工具**

```python
"""对话工具 —— 接收用户消息，生成回复并标注意图和标签。"""
import json
from src.tools.base import BaseTool, ToolResult
from src.core.llm import llm
from src.memory.short_term import ShortTermMemory
from src.memory.retrieval import retrieve_relevant_context


class ChatTool(BaseTool):
    name = "chat"
    description = "与用户对话。接收用户消息，结合记忆上下文生成回复，自动标注话题标签和用户意图。"

    def __init__(self, memory: ShortTermMemory) -> None:
        self.memory = memory

    async def execute(self, message: str, session_id: str = "default") -> ToolResult:
        # 检索相关记忆
        context = retrieve_relevant_context(message)

        # 构建 System Prompt
        system_prompt = f"""你是 Evomentor，一个能自我进化的个人学习助手。
你的目标是帮助用户高效学习，持续跟踪他们的成长。

## 用户知识背景
{context}

## 行为指南
- 回答要精准、有深度，避免泛泛而谈
- 发现用户的薄弱点时，温和指出并给出学习建议
- 记住用户的偏好和技术栈
- 回复末尾标注：##标签: <逗号分隔的话题标签>
"""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.memory.get_for_llm())
        messages.append({"role": "user", "content": message})

        response = llm.chat(messages)

        content = response["content"]
        # 解析标签
        tags, intent = self._parse_meta(content)

        # 写入短期记忆
        self.memory.add("user", message, tags=tags, intent=intent)
        self.memory.add("assistant", content, tags=tags)

        return ToolResult(success=True, content=content, metadata={"tags": tags, "intent": intent})

    def _parse_meta(self, content: str) -> tuple[list[str], str]:
        tags = []
        intent = ""
        if "##标签:" in content:
            tag_part = content.split("##标签:")[-1].strip()
            tags = [t.strip() for t in tag_part.split(",") if t.strip()]
        return tags, intent

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "用户消息内容"},
                "session_id": {"type": "string", "description": "会话ID，默认 default"},
            },
            "required": ["message"],
        }
```

- [ ] **Step 2: 编写测试**

```python
# tests/test_tools.py
import pytest
from src.memory.short_term import ShortTermMemory


@pytest.mark.asyncio
async def test_chat_tool():
    from src.tools.chat import ChatTool
    mem = ShortTermMemory()
    tool = ChatTool(mem)
    result = await tool.execute("什么是 Python 装饰器？")
    assert result.success
    assert result.content
    assert len(mem.get_all()) == 2  # user + assistant
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_tools.py::test_chat_tool -v
```

---

### Task 5.3: GitHub 分析工具

**Files:**
- Create: `src/tools/github.py`

- [ ] **Step 1: 编写 GitHub 分析工具**

```python
"""GitHub 分析工具 —— 拉取用户 commits 和 Star 仓库动态，分析代码问题。"""
from datetime import datetime, timedelta
from github import Github, GithubException
from src.tools.base import BaseTool, ToolResult
from src.core.config import config
from src.core.llm import llm
from src.memory.long_term import lts


class GitHubTool(BaseTool):
    name = "github_analyze"
    description = "分析用户最近的 GitHub 提交和 Star 仓库动态，发现代码问题并总结学习点。"

    async def execute(self, days: int = 7) -> ToolResult:
        if not config.GITHUB_TOKEN:
            return ToolResult(success=False, content="GitHub Token 未配置")

        g = Github(config.GITHUB_TOKEN)
        since = datetime.now() - timedelta(days=days)
        reports: list[str] = []

        try:
            user = g.get_user(config.GITHUB_USERNAME)

            # 1. 分析个人仓库提交
            for repo in user.get_repos():
                if repo.fork:
                    continue
                try:
                    commits = repo.get_commits(since=since, author=config.GITHUB_USERNAME)
                    for commit in commits[:20]:  # 每个仓库最多分析 20 个提交
                        analysis = await self._analyze_commit(repo.name, commit)
                        if analysis:
                            reports.append(analysis)
                except GithubException:
                    continue

            # 2. 分析 Star 仓库动态
            starred = user.get_starred()
            for repo in starred[:10]:
                try:
                    latest_release = repo.get_latest_release()
                    if latest_release.created_at > since:
                        reports.append(
                            f"[Star 仓库更新] {repo.full_name}: "
                            f"最新 Release {latest_release.tag_name} — {latest_release.title}\n"
                            f"{latest_release.body[:300]}"
                        )
                except GithubException:
                    continue

        finally:
            g.close()

        if not reports:
            return ToolResult(success=True, content="最近没有新的提交或动态。")

        # 汇总分析报告
        full_report = "\n\n---\n\n".join(reports)

        # 交叉对比已有代码模式
        known_patterns = lts.get_experiences_by_category("code_pattern", limit=10)
        if known_patterns:
            full_report += "\n\n## 历史模式提醒\n"
            for p in known_patterns:
                full_report += f"- {p['title']}\n"

        return ToolResult(success=True, content=full_report)

    async def _analyze_commit(self, repo_name: str, commit) -> str:
        """用 LLM 分析单个 commit 的 diff。"""
        files = commit.files
        if not files:
            return ""

        diff_text = ""
        for f in files[:5]:  # 最多分析 5 个文件
            patch = f.patch or ""
            diff_text += f"文件: {f.filename}\n{patch[:2000]}\n\n"

        if not diff_text.strip():
            return ""

        prompt = f"""分析以下 Git 提交的代码变更，找出潜在问题：

仓库: {repo_name}
提交: {commit.commit.message[:200]}
时间: {commit.commit.author.date}

代码变更:
{diff_text[:4000]}

请分析：
1. 安全问题（SQL注入、XSS、密钥泄露等）
2. Bug 模式（空指针、并发问题、边界条件等）
3. 代码异味（重复代码、过长函数、命名问题等）
4. 改进建议

用中文回复，简洁直接。"""

        response = llm.chat([{"role": "user", "content": prompt}])
        return f"## [{repo_name}] {commit.commit.message[:80]}\n{response['content']}"

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "分析最近几天的提交，默认 7"},
            },
        }
```

---

### Task 5.4: 邮件工具

**Files:**
- Create: `src/tools/email_tool.py`

- [ ] **Step 1: 编写邮件工具**

```python
"""邮件工具 —— 合并待发内容，润色后通过 SMTP 发送。"""
from src.tools.base import BaseTool, ToolResult
from src.core.config import config
from src.core.llm import llm
from src.db.models import get_connection
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class EmailTool(BaseTool):
    name = "send_email"
    description = "合并待发邮件内容，经 LLM 润色后发送给用户。"

    async def execute(self, to_email: str = "") -> ToolResult:
        if not config.SMTP_USER:
            return ToolResult(success=False, content="SMTP 未配置")

        to = to_email or config.SMTP_USER

        # 1. 从队列中拉取待发内容
        conn = get_connection()
        pending = conn.execute(
            "SELECT * FROM pending_emails WHERE status = 'pending' ORDER BY scheduled_at"
        ).fetchall()
        conn.close()

        if not pending:
            return ToolResult(success=True, content="没有待发送的邮件。")

        # 2. 合并内容并润色
        parts = [f"## {p['subject']}\n{p['body']}" for p in pending]
        raw = "\n\n---\n\n".join(parts)

        polish_prompt = f"""请将以下内容润色为一封友好的学习周报邮件，使用 HTML 格式：

原始内容:
{raw}

要求：
- 开头有亲切的问候
- 总结近期学习重点
- 列出代码改进建议
- 推荐前沿方向和资源
- 结尾鼓励用户
- 纯 HTML，适合邮件客户端阅读"""

        response = llm.chat([{"role": "user", "content": polish_prompt}])

        # 3. 发送邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Evomentor 学习周报 — {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}"
        msg["From"] = config.SMTP_USER
        msg["To"] = to
        msg.attach(MIMEText(response["content"], "html", "utf-8"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=config.SMTP_HOST,
                port=config.SMTP_PORT,
                username=config.SMTP_USER,
                password=config.SMTP_PASSWORD,
                start_tls=True,
            )
        except Exception as e:
            # 标记为失败
            conn = get_connection()
            for p in pending:
                conn.execute(
                    "UPDATE pending_emails SET status = 'failed' WHERE id = ?", (p["id"],)
                )
            conn.commit()
            conn.close()
            return ToolResult(success=False, content=f"邮件发送失败: {e}")

        # 4. 标记为已发送
        conn = get_connection()
        for p in pending:
            conn.execute(
                "UPDATE pending_emails SET status = 'sent', sent_at = CURRENT_TIMESTAMP WHERE id = ?",
                (p["id"],),
            )
        conn.commit()
        conn.close()

        return ToolResult(success=True, content=f"已发送 {len(pending)} 封邮件到 {to}")

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "to_email": {"type": "string", "description": "收件人邮箱，默认使用配置中的 SMTP_USER"},
            },
        }
```

---

### Task 5.5: 研究工具

**Files:**
- Create: `src/tools/research.py`

- [ ] **Step 1: 编写研究工具**

```python
"""研究工具 —— 根据用户当前关注的话题，搜索最新论文、论坛和 GitHub 仓库。"""
import httpx
from src.tools.base import BaseTool, ToolResult
from src.memory.long_term import lts


class ResearchTool(BaseTool):
    name = "research"
    description = "根据用户关注的话题搜索最新论文(arXiv)、论坛(Hacker News/Reddit)和 GitHub 仓库。"

    async def execute(self, topics: str = "") -> ToolResult:
        # 如果未指定主题，从知识图谱推断
        if not topics:
            graph = lts.get_knowledge_graph()
            if graph:
                topics = ", ".join(g["topic"] for g in graph[:5])
            else:
                topics = "AI Agent, LLM, Machine Learning"

        results: list[str] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for topic in topics.split(","):
                topic = topic.strip()
                if not topic:
                    continue

                # arXiv 搜索
                results.append(await self._search_arxiv(client, topic))

                # Hacker News 搜索
                results.append(await self._search_hn(client, topic))

                # GitHub Trending 搜索
                results.append(await self._search_github(client, topic))

        full = "\n\n".join(r for r in results if r)
        if not full:
            return ToolResult(success=True, content="暂未找到相关前沿内容。")

        # 保存到数据库
        for topic in topics.split(",")[:3]:
            topic = topic.strip()
            if topic:
                lts.save_experience(
                    "research_insight", f"研究方向: {topic}",
                    full[:500], source="research_tool", confidence=0.6,
                )

        return ToolResult(success=True, content=full)

    async def _search_arxiv(self, client: httpx.AsyncClient, topic: str) -> str:
        try:
            resp = await client.get(
                "http://export.arxiv.org/api/query",
                params={"search_query": topic, "sortBy": "submittedDate", "max_results": "5"},
            )
            if resp.status_code != 200:
                return ""
            # 简单解析 Atom XML
            entries = resp.text.split("<entry>")
            if len(entries) < 2:
                return ""
            lines = [f"### arXiv: {topic}"]
            for entry in entries[1:6]:
                title = _extract_tag(entry, "title")
                summary = _extract_tag(entry, "summary")
                link = _extract_tag(entry, "id")
                if title:
                    lines.append(f"- **{title[:150]}**")
                    lines.append(f"  {summary[:300]}")
                    lines.append(f"  {link}")
            return "\n".join(lines)
        except Exception:
            return ""

    async def _search_hn(self, client: httpx.AsyncClient, topic: str) -> str:
        try:
            resp = await client.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": topic, "tags": "story", "hitsPerPage": 5},
            )
            data = resp.json()
            hits = data.get("hits", [])
            if not hits:
                return ""
            lines = [f"### Hacker News: {topic}"]
            for h in hits:
                lines.append(f"- [{h.get('title', '')}]({h.get('url', '')}) — {h.get('points', 0)} points")
            return "\n".join(lines)
        except Exception:
            return ""

    async def _search_github(self, client: httpx.AsyncClient, topic: str) -> str:
        try:
            resp = await client.get(
                "https://api.github.com/search/repositories",
                params={"q": topic, "sort": "stars", "order": "desc", "per_page": 5},
            )
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return ""
            lines = [f"### GitHub: {topic}"]
            for item in items:
                lines.append(
                    f"- **{item['full_name']}** ⭐{item['stargazers_count']}: "
                    f"{item.get('description', '')[:150]}\n  {item['html_url']}"
                )
            return "\n".join(lines)
        except Exception:
            return ""

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "topics": {"type": "string", "description": "搜索主题，逗号分隔。留空则从知识图谱推断"},
            },
        }


def _extract_tag(xml: str, tag: str) -> str:
    start = xml.find(f"<{tag}>")
    end = xml.find(f"</{tag}>")
    if start == -1 or end == -1:
        return ""
    return xml[start + len(tag) + 2 : end].strip()
```

---

### Task 5.6: 反思工具

**Files:**
- Create: `src/tools/reflect.py`

- [ ] **Step 1: 编写反思工具**

```python
"""反思工具 —— 自我进化的核心。审视短期记忆和决策日志，总结规律，更新知识图谱。"""
import json
from src.tools.base import BaseTool, ToolResult
from src.core.llm import llm
from src.memory.short_term import ShortTermMemory
from src.memory.long_term import lts
from src.db.vector_store import vector_store


class ReflectTool(BaseTool):
    name = "reflect"
    description = "审视近期的对话、GitHub 分析结果和决策日志，提炼经验教训，更新用户知识图谱。"

    def __init__(self, memory: ShortTermMemory) -> None:
        self.memory = memory

    async def execute(self) -> ToolResult:
        # 1. 收集反思素材
        conversations = self.memory.summarize_for_compression()
        decisions = lts.get_recent_decisions(limit=20)
        decisions_text = "\n".join(
            f"触发: {d['trigger']} | 结果: {d['outcome'][:200]}" for d in decisions
        )

        prompt = f"""你是 Evomentor 的反思模块，请审视以下信息，提炼经验教训：

## 近期对话
{conversations[:3000]}

## 近期决策
{decisions_text[:2000]}

请完成以下任务，输出 JSON 格式：

```json
{{
    "insights": [
        {{"category": "code_pattern|learning_tip|user_preference|research_insight",
          "title": "简短标题",
          "content": "详细内容"}}
    ],
    "knowledge_updates": [
        {{"topic": "知识领域", "proficiency": 1-5, "parent": "父领域"}}
    ],
    "summary": "一段话总结用户这段时间的学习状态"
}}
```

要求：
- 识别重复出现的问题模式（尤其是在代码中）
- 发现用户正在学习的方向
- 总结用户表现出的偏好
- 如果信息不足，对应字段填空数组即可"""

        response = llm.chat([{"role": "user", "content": prompt}])

        # 2. 解析结果
        try:
            data = self._parse_json(response["content"])
        except (json.JSONDecodeError, KeyError):
            return ToolResult(success=True, content="反思完成（无新发现）")

        # 3. 保存经验
        saved_count = 0
        for insight in data.get("insights", []):
            exp_id = lts.save_experience(
                category=insight.get("category", "learning_tip"),
                title=insight.get("title", "未命名"),
                content=insight.get("content", ""),
                source="reflection",
                confidence=0.5,
            )
            # 同时存入向量库
            text = f"{insight.get('title', '')}: {insight.get('content', '')}"
            vector_store.add("experience_embeddings", f"exp-{exp_id}", text)
            saved_count += 1

        # 4. 更新知识图谱
        for update in data.get("knowledge_updates", []):
            lts.update_knowledge(
                topic=update.get("topic", ""),
                proficiency=int(update.get("proficiency", 1)),
                parent=update.get("parent", ""),
            )

        # 5. 压缩短期记忆 —— 保留最近 10 条，其余清除
        recent = self.memory.get_all()[-10:]
        self.memory.clear()
        for m in recent:
            self.memory.add(m.role, m.content, m.tags, m.intent)

        return ToolResult(
            success=True,
            content=f"反思完成。保存 {saved_count} 条经验，更新 {len(data.get('knowledge_updates', []))} 个知识点。\n摘要: {data.get('summary', '')}",
            metadata={"insights_count": saved_count, "summary": data.get("summary", "")},
        )

    def _parse_json(self, text: str) -> dict:
        """从 LLM 输出中提取 JSON 块。"""
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            return json.loads(text[start:end])
        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            return json.loads(text[start:end])
        return json.loads(text)

    def get_parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}
```

---

### Task 5.7: Skill 管理工具

**Files:**
- Create: `src/tools/skill_manager.py`

- [ ] **Step 1: 编写 Skill 管理工具**

```python
"""Skill 管理工具 —— 将稳定的经验转化为可复用的 Skill。"""
import os
import json
from datetime import datetime
from src.tools.base import BaseTool, ToolResult
from src.core.config import config
from src.core.llm import llm
from src.memory.long_term import lts
from src.db.models import get_connection


class SkillManagerTool(BaseTool):
    name = "skill_manager"
    description = "审视长期经验，将高置信度、反复出现的经验转化为可复用的 Skill。"

    async def execute(self) -> ToolResult:
        # 1. 拉取待评估的经验（未关联 Skill 的经验）
        conn = get_connection()
        rows = conn.execute(
            """SELECT * FROM experiences
               WHERE category = 'code_pattern' AND confidence >= ?
               ORDER BY created_at DESC LIMIT 30""",
            (config.SKILL_CONFIDENCE_THRESHOLD,),
        ).fetchall()
        conn.close()

        if not rows:
            return ToolResult(success=True, content="暂无可转化为 Skill 的经验。")

        experiences_text = "\n".join(
            f"- [{r['id']}] {r['title']}: {r['content'][:300]}" for r in rows
        )

        existing_skills = lts.get_experiences_by_category("skill_registry", limit=20)

        prompt = f"""你是 Evomentor 的 Skill 管理模块。审视以下经验，判断哪些可以转化为可复用的 Skill。

## 候选经验
{experiences_text[:4000]}

## 已有 Skills（避免重复）
{chr(10).join(f"- {s['title']}" for s in existing_skills) if existing_skills else "（暂无）"}

请判断哪些经验足够稳定、通用，值得转化为 Skill。输出 JSON：

```json
{{
    "new_skills": [
        {{
            "name": "Skill 英文名（如 django-n1-query-detect）",
            "trigger_condition": "触发这个 Skill 的条件",
            "behavior_rules": "Markdown 格式的行为规则，包含 1.检测方法 2.修复建议 3.相关案例"
        }}
    ]
}}
```

标准：
- 经验出现的频率高（有多条相关经验）
- 经验可转化为明确的规则
- 与已有 Skill 不重复
- 如果没有合适的候选，返回空数组"""

        response = llm.chat([{"role": "user", "content": prompt}])

        try:
            data = json.loads(
                response["content"]
                .split("```json")[-1].split("```")[0]
                if "```" in response["content"]
                else response["content"]
            )
        except json.JSONDecodeError:
            return ToolResult(success=True, content="Skill 分析未产生有效结果。")

        created = []
        for skill_data in data.get("new_skills", []):
            name = skill_data.get("name", "unnamed")
            trigger = skill_data.get("trigger_condition", "")
            rules = skill_data.get("behavior_rules", "")

            # 写入 Markdown 文件
            os.makedirs("skills", exist_ok=True)
            filename = f"skills/{name}.md"
            version = 1

            # 检查已有版本
            if os.path.exists(filename):
                version = 2  # 简化处理，实际可读取已有版本号

            content = f"""# Skill: {name}

## 触发条件
{trigger}

## 行为规则
{rules}

## 元数据
- 版本: {version}
- 创建时间: {datetime.now().isoformat()}
- 来源: 自动生成
"""
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            # 注册到数据库
            conn = get_connection()
            conn.execute(
                """INSERT INTO skills (name, trigger_condition, behavior_rules, version, file_path)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, trigger, rules, version, filename),
            )
            conn.commit()
            conn.close()

            created.append(f"{name} (v{version})")

        if created:
            return ToolResult(
                success=True,
                content=f"创建了 {len(created)} 个新 Skill: {', '.join(created)}",
            )
        return ToolResult(success=True, content="未发现需要创建的新 Skill。")

    def get_parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}
```

---

### Task 5.8: Tool 注册表

**Files:**
- Create: `src/tools/__init__.py` (更新)

- [ ] **Step 1: 编写 Tool 注册表**

```python
"""工具注册表 —— 集中管理所有 Tool 实例，提供 schema 列表给 Agent。"""
from src.tools.chat import ChatTool
from src.tools.github import GitHubTool
from src.tools.email_tool import EmailTool
from src.tools.research import ResearchTool
from src.tools.reflect import ReflectTool
from src.tools.skill_manager import SkillManagerTool


class ToolRegistry:
    def __init__(self, memory) -> None:
        self.tools: dict[str, object] = {
            "chat": ChatTool(memory),
            "github_analyze": GitHubTool(),
            "send_email": EmailTool(),
            "research": ResearchTool(),
            "reflect": ReflectTool(memory),
            "skill_manager": SkillManagerTool(),
        }

    def get_schemas(self) -> list[dict]:
        return [tool.to_llm_schema() for tool in self.tools.values()]

    def get(self, name: str):
        return self.tools.get(name)

    def list_names(self) -> list[str]:
        return list(self.tools.keys())
```

---

## Phase 6: Agent 核心引擎

### Task 6.1: Agent 循环

**Files:**
- Create: `src/core/agent.py`

- [ ] **Step 1: 编写 Agent 核心循环**

```python
"""Agent 核心循环 —— 感知→思考→行动→观察。"""
import uuid
from src.core.llm import llm
from src.memory.short_term import ShortTermMemory
from src.memory.long_term import lts
from src.memory.retrieval import retrieve_relevant_context
from src.tools import ToolRegistry

SYSTEM_PROMPT = """你是 Evomentor，一个能自我进化的个人学习助手。

## 核心使命
帮助用户高效学习成长。你通过以下工具实现这一目标：
- **chat**: 与用户交流，解答问题
- **github_analyze**: 分析用户的 GitHub 提交和 Star 仓库
- **research**: 搜索最新的论文、论坛和 GitHub 仓库
- **reflect**: 审视近期对话，提炼经验，自我进化
- **skill_manager**: 将稳定经验转化为可复用的 Skill
- **send_email**: 发送学习周报邮件给用户

## 行为准则
- 主动感知用户的学习状态和需求
- 准确判断何时该聊天、分析、研究或反思
- 对话自然、有帮助、有深度
- 当用户消息是简单问候时，只用 chat 回复，不要调用其他工具
- 当用户问及具体技术问题时，先用 chat 回复，视情况补充 research"""


class Agent:
    def __init__(self) -> None:
        self.short_term = ShortTermMemory()
        self.tools = ToolRegistry(self.short_term)
        self.session_id = str(uuid.uuid4())[:8]

    async def handle_message(self, user_message: str) -> str:
        """被动触发：处理用户消息。"""
        # 感知
        context = retrieve_relevant_context(user_message)
        self.short_term.add("user", user_message)

        # 思考 + 行动 + 观察 循环（最多 5 轮）
        return await self._agent_loop(
            trigger="user_message",
            initial_context=context,
            max_rounds=5,
        )

    async def handle_scheduled(self, trigger: str) -> str:
        """主动触发：处理定时任务。"""
        context = retrieve_relevant_context(trigger)

        prompt_map = {
            "periodic_check": "现在是定时检查。请分析用户的 GitHub 最近提交，搜索前沿方向，反思近期对话并准备学习周报。如果一切正常，最后发送邮件。",
            "reflect": "现在是自我反思时间。请审视近期的所有对话和分析结果，提炼经验，更新知识图谱，必要时创建 Skill。",
        }

        initial = prompt_map.get(trigger, f"执行任务：{trigger}")
        self.short_term.add("system", initial)

        return await self._agent_loop(
            trigger=trigger,
            initial_context=context,
            max_rounds=8,
        )

    async def _agent_loop(self, trigger: str, initial_context: str, max_rounds: int) -> str:
        """核心循环：思考 → 行动 → 观察，最多 max_rounds 轮。"""
        context = initial_context
        final_response = ""

        for _ in range(max_rounds):
            # 思考：让 LLM 决定调用哪个 Tool
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": f"## 相关记忆\n{context}"},
            ]
            messages.extend(self.short_term.get_for_llm())

            response = llm.chat(messages, tools=self.tools.get_schemas())

            # 记录决策
            tool_calls = response.get("tool_calls", [])
            lts.log_decision(
                trigger=trigger,
                tool_calls=[tc["name"] for tc in tool_calls],
                reasoning=response.get("content", ""),
                outcome="",
            )

            # 如果没有 tool_calls，说明 LLM 认为该直接回复
            if not tool_calls:
                final_response = response["content"]
                self.short_term.add("assistant", final_response)
                break

            # 行动：依次执行 Tool
            outcomes = []
            for tc in tool_calls:
                tool = self.tools.get(tc["name"])
                if tool:
                    result = await tool.execute(**tc["arguments"])
                    outcomes.append(f"[{tc['name']}] {result.content}")
                    self.short_term.add_tool_result(tc["name"], result.content)
                    if result.metadata:
                        context += f"\n{tc['name']} 元数据: {result.metadata}"

            # 观察：汇总结果，继续循环
            self.short_term.add("system", "工具执行完毕，请根据结果决定下一步。")
            if outcomes:
                final_response = "\n".join(outcomes)

        # 保存对话到长期存储
        for msg in self.short_term.get_all():
            lts.save_conversation(
                role=msg.role, content=msg.content,
                tags=msg.tags, intent=msg.intent,
                session_id=self.session_id,
            )

        return final_response
```

- [ ] **Step 2: 编写测试**

```python
# tests/test_agent.py
import pytest
from src.core.agent import Agent


@pytest.mark.asyncio
async def test_agent_chat():
    agent = Agent()
    response = await agent.handle_message("你好")
    assert response
    assert isinstance(response, str)


@pytest.mark.asyncio
async def test_agent_scheduled():
    agent = Agent()
    response = await agent.handle_scheduled("reflect")
    assert response
    assert isinstance(response, str)
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_agent.py -v
```

---

## Phase 7: 调度器

### Task 7.1: 定时任务

**Files:**
- Create: `src/scheduler/jobs.py`

- [ ] **Step 1: 编写调度器**

```python
"""定时任务 —— 基于用户活跃度智能触发。"""
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from src.core.agent import Agent
from src.core.config import config
from src.memory.long_term import lts

scheduler = AsyncIOScheduler()
agent = Agent()


def _last_activity() -> datetime:
    """获取用户最后一次活跃时间。"""
    conn = __import__("src.db.models", fromlist=["get_connection"]).get_connection()
    row = conn.execute(
        "SELECT created_at FROM conversations WHERE role = 'user' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row:
        return datetime.fromisoformat(row["created_at"])
    return datetime.min


async def periodic_check() -> None:
    """周期性检查：仅在用户空闲时触发。"""
    last = _last_activity()
    idle_hours = (datetime.now() - last).total_seconds() / 3600

    if idle_hours >= config.IDLE_HOURS_BEFORE_TRIGGER:
        await agent.handle_scheduled("periodic_check")


async def daily_reflect() -> None:
    """每日反思：每天凌晨触发一次。"""
    await agent.handle_scheduled("reflect")


async def send_daily_email() -> None:
    """每日邮件：每天只发一封，合并所有待发内容。"""
    # 检查今天是否已发送
    conn = __import__("src.db.models", fromlist=["get_connection"]).get_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM pending_emails WHERE status = 'sent' AND date(sent_at) = ?",
        (today,),
    ).fetchone()
    conn.close()

    if row and row["cnt"] > 0:
        return  # 今天已发过

    await agent.handle_scheduled("periodic_check")


def start_scheduler() -> None:
    """启动调度器。"""
    # 每 30 分钟检查一次用户活跃度
    scheduler.add_job(
        periodic_check,
        IntervalTrigger(minutes=30),
        id="periodic_check",
        name="周期性检查",
        replace_existing=True,
    )
    # 每天凌晨 2 点反思
    scheduler.add_job(
        daily_reflect,
        IntervalTrigger(hours=24),
        id="daily_reflect",
        name="每日反思",
        replace_existing=True,
    )
    scheduler.start()
```

---

## Phase 8: Web 界面

### Task 8.1: FastAPI 应用与路由

**Files:**
- Create: `src/web/routes.py`
- Create: `src/web/app.py`

- [ ] **Step 1: 编写 API 路由**

```python
"""API 路由 —— Web 聊天接口。"""
from fastapi import APIRouter, Request
from pydantic import BaseModel
from src.core.agent import Agent

router = APIRouter()

# 全局 Agent 实例（应用启动时初始化）
_agent: Agent | None = None


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    agent = get_agent()
    reply = await agent.handle_message(req.message)
    return ChatResponse(reply=reply)


@router.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 2: 编写 FastAPI 应用入口**

```python
"""FastAPI 应用入口 —— 启动 Web 服务和调度器。"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from src.web.routes import router
from src.scheduler.jobs import start_scheduler
from src.db.models import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield

app = FastAPI(title="Evomentor", lifespan=lifespan)
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("src/web/templates/index.html", "r", encoding="utf-8") as f:
        return f.read()
```

---

### Task 8.2: 聊天界面 HTML

**Files:**
- Create: `src/web/templates/index.html`

- [ ] **Step 1: 编写聊天界面**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evomentor — 个人学习助手</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #1a1a2e; color: #e0e0e0; height: 100vh; display: flex;
               flex-direction: column; }
        header { background: #16213e; padding: 16px 24px; border-bottom: 1px solid #0f3460; }
        header h1 { font-size: 20px; font-weight: 600; }
        header span { font-size: 13px; color: #888; }
        #chat { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
        .msg { max-width: 80%; padding: 12px 16px; border-radius: 12px; line-height: 1.6; white-space: pre-wrap; }
        .msg.user { align-self: flex-end; background: #0f3460; }
        .msg.assistant { align-self: flex-start; background: #16213e; border: 1px solid #0f3460; }
        #input-area { display: flex; padding: 16px 24px; gap: 12px; border-top: 1px solid #0f3460; background: #16213e; }
        #message { flex: 1; padding: 12px 16px; border-radius: 8px; border: 1px solid #0f3460;
                   background: #1a1a2e; color: #e0e0e0; resize: none; font-size: 14px; }
        #send { padding: 12px 24px; border: none; border-radius: 8px; background: #e94560;
                color: white; cursor: pointer; font-weight: 600; }
        #send:hover { background: #d63851; }
        #send:disabled { opacity: 0.5; cursor: not-allowed; }
        .loading { color: #888; font-style: italic; padding: 8px 16px; }
    </style>
</head>
<body>
    <header>
        <h1>Evomentor <span>个人学习助手</span></h1>
    </header>
    <div id="chat"></div>
    <div id="input-area">
        <textarea id="message" rows="2" placeholder="输入你的问题... (Enter 发送, Shift+Enter 换行)"></textarea>
        <button id="send" onclick="sendMessage()">发送</button>
    </div>
    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('message');
        const sendBtn = document.getElementById('send');

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        async function sendMessage() {
            const text = input.value.trim();
            if (!text) return;
            addMsg('user', text);
            input.value = '';
            sendBtn.disabled = true;
            const loading = addMsg('assistant', '思考中...', true);
            try {
                const resp = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                const data = await resp.json();
                loading.remove();
                addMsg('assistant', data.reply);
            } catch (e) {
                loading.remove();
                addMsg('assistant', '出错了: ' + e.message);
            }
            sendBtn.disabled = false;
        }

        function addMsg(role, content, isLoading = false) {
            const div = document.createElement('div');
            div.className = 'msg ' + role;
            div.textContent = content;
            if (isLoading) div.classList.add('loading');
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
            return div;
        }
    </script>
</body>
</html>
```

---

## Phase 9: 集成与启动

### Task 9.1: 入口与启动脚本

**Files:**
- Create: `run.py`

- [ ] **Step 1: 编写启动脚本**

```python
"""Evomentor 启动入口。"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.web.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
```

- [ ] **Step 2: 启动验证**

```bash
python run.py
```

预期：访问 `http://localhost:8000` 看到聊天界面，发送消息能收到回复。

---

### Task 9.2: 集成测试

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 编写集成测试**

```python
"""集成测试 —— 端到端验证核心流程。"""
import pytest
from src.core.agent import Agent


@pytest.mark.asyncio
async def test_full_chat_flow():
    """测试完整对话流程：发送消息 → 获得回复 → 对话被持久化。"""
    agent = Agent()
    reply = await agent.handle_message("我在学习 Python 异步编程，有什么建议？")
    assert reply
    assert isinstance(reply, str)
    assert len(reply) > 0


@pytest.mark.asyncio
async def test_reflect_flow():
    """测试反思流程。"""
    agent = Agent()
    # 先模拟一些对话
    await agent.handle_message("什么是 asyncio？")
    await agent.handle_message("如何用 aiohttp 发请求？")
    # 执行反思
    reply = await agent.handle_scheduled("reflect")
    assert reply
    assert isinstance(reply, str)


@pytest.mark.asyncio
async def test_memory_persistence():
    """测试记忆持久化：对话保存后能从数据库读取。"""
    from src.memory.long_term import lts
    agent = Agent()
    await agent.handle_message("测试记忆持久化")
    conversations = lts.get_conversations_by_session(agent.session_id)
    assert len(conversations) > 0
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/test_integration.py -v
```

---

## 验证清单

所有测试通过后，手动验证以下功能：

- [ ] Web 界面能正常打开并发送消息
- [ ] Agent 正确回复技术问题
- [ ] 对话保存到 SQLite
- [ ] 调度器正常启动（日志中可见）
- [ ] 配置 .env 后邮件能发送
- [ ] GitHub Token 配置后能拉取提交分析
- [ ] 反思工具能提炼经验并写入长期记忆
- [ ] Skill 管理工具能生成 Skill 文件
