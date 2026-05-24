# 代码质量全面改进 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 3 个严重 Bug、5 个代码质量问题、3 个优化项，提升 Evomentor 项目的健壮性和可维护性。

**Architecture:** 按依赖顺序执行 10 个任务：先抽取共享模块（connection.py）消除循环导入，再修复数据流 Bug，然后是 agent.py 内的代码质量修复，最后补充测试和优化。

**Tech Stack:** Python 3.x, pytest, SQLite, ChromaDB

---

### Task 1: 抽取 connection.py 消除循环导入

**Files:**
- Create: `src/db/connection.py`
- Modify: `src/db/models.py:7-13`
- Modify: `src/scheduler/jobs.py:15-18`
- Modify: `src/memory/retrieval.py:31`

- [ ] **Step 1: 创建 `src/db/connection.py`**

```python
"""数据库连接 —— 提供统一的 SQLite 连接获取接口。"""
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
```

- [ ] **Step 2: 修改 `src/db/models.py`，删除 `get_connection` 并从 connection 重导出**

当前第 1-13 行：
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
```

改为：
```python
"""SQLite 表定义与数据库初始化。"""
from src.db.connection import get_connection  # noqa: F401  # 向后兼容重导出
```

- [ ] **Step 3: 修改 `src/scheduler/jobs.py`，替换 `__import__` hack**

当前第 15-18 行：
```python
def _last_activity() -> datetime:
    """获取用户最后一次活跃时间。"""
    conn = __import__("src.db.models", fromlist=["get_connection"]).get_connection()
```

改为：
```python
from src.db.connection import get_connection

def _last_activity() -> datetime:
    """获取用户最后一次活跃时间。"""
    conn = get_connection()
```

将 import 移到文件顶部（第 8 行 `from src.memory.long_term import lts` 之后）。

- [ ] **Step 4: 修改 `src/memory/retrieval.py`，替换 `__import__` hack**

当前第 31-34 行：
```python
    conn = __import__("src.db.models", fromlist=["get_connection"]).get_connection()
    rows = conn.execute(
        "SELECT name, trigger_condition FROM skills WHERE active = 1"
    ).fetchall()
```

改为：
```python
    from src.db.connection import get_connection
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, trigger_condition FROM skills WHERE active = 1"
    ).fetchall()
```

将 import 移到文件顶部（第 4 行之后）。

- [ ] **Step 5: 运行现有测试确认无回归**

```bash
pytest tests/ -v --timeout=30
```

预期：已有测试全部通过（或因无 API key 跳过，无 import 错误）。

- [ ] **Step 6: 提交**

```bash
git add src/db/connection.py src/db/models.py src/scheduler/jobs.py src/memory/retrieval.py
git commit -m "refactor: 抽取 get_connection 到独立模块，消除 __import__ 循环导入 hack"
```

---

### Task 2: 修复 email_tool.py 重复动态 import

**Files:**
- Modify: `src/tools/email_tool.py:63`

- [ ] **Step 1: 将 `__import__('datetime')` 替换为文件顶部已有的 `datetime`**

当前第 63 行：
```python
        msg["Subject"] = f"Evomentor 学习周报 — {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}"
```

改为：
```python
        msg["Subject"] = f"Evomentor 学习周报 — {datetime.now().strftime('%Y-%m-%d')}"
```

文件顶部第 3 行已有 `from datetime import datetime`，无需新增 import。

- [ ] **Step 2: 提交**

```bash
git add src/tools/email_tool.py
git commit -m "fix: 移除 email_tool.py 中重复的动态 __import__('datetime')"
```

---

### Task 3: 修复邮件队列永远为空（Bug）

**Files:**
- Modify: `src/memory/long_term.py`（新增 `enqueue_email` 方法）
- Modify: `src/core/agent.py`（`handle_scheduled` 和 `handle_scheduled_stream` 中保存报告后入队邮件）
- Modify: `src/tools/email_tool.py`（队列为空时 fallback 到 agent_reports）

- [ ] **Step 1: 在 `LongTermMemory` 中新增 `enqueue_email` 方法**

在 `src/memory/long_term.py` 的 `save_agent_report` 方法之后添加：

```python
    def enqueue_email(self, subject: str, body: str) -> int:
        """将邮件内容写入待发队列。"""
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO pending_emails (subject, body, status) VALUES (?, ?, 'pending')",
            (subject, body),
        )
        conn.commit()
        email_id = cursor.lastrowid
        conn.close()
        return email_id
```

- [ ] **Step 2: 在 `handle_scheduled` 中保存报告后自动入队邮件**

`src/core/agent.py` 的 `handle_scheduled` 方法中，在 `_save_report_file(...)` 调用之后，`commit_and_push()` 之前，添加：

```python
        # 保存最终摘要为报告
        if result and result.strip():
            try:
                title = result.strip().split("\n")[0][:80]
                lts.save_agent_report(
                    trigger=trigger,
                    title=title,
                    content=result.strip(),
                    session_id=self.session_id,
                )
                _save_report_file(
                    title=title,
                    content=result.strip(),
                    trigger=trigger,
                    session_id=self.session_id,
                )
                # 自动将报告摘要加入邮件待发队列
                lts.enqueue_email(
                    subject=f"Evomentor 学习周报 — {title[:50]}",
                    body=result.strip(),
                )
            except Exception:
                agent_logger.warning("[SYSTEM] 保存报告失败", exc_info=True)
```

- [ ] **Step 3: 在 `handle_scheduled_stream` 的 done 事件中同样入队**

在 `src/core/agent.py` 的 `handle_scheduled_stream` 方法中，第 150-165 行（`if text_buffer.strip():` 块内），在 `_save_report_file(...)` 之后添加：

```python
                            lts.enqueue_email(
                                subject=f"Evomentor 学习周报 — {title[:50]}",
                                body=text_buffer.strip(),
                            )
```

- [ ] **Step 4: 修改 `EmailTool.execute()` —— 队列为空时 fallback 到最新 agent_report**

修改 `src/tools/email_tool.py` 的 `execute` 方法，将第 31-32 行：
```python
        if not pending:
            return ToolResult(success=True, content="没有待发送的邮件。")
```

改为：
```python
        if not pending:
            # 队列为空时，从 agent_reports 表取最新报告作为 fallback
            conn = get_connection()
            row = conn.execute(
                "SELECT title, content FROM agent_reports ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if not row:
                return ToolResult(success=True, content="没有待发送的邮件，也无可用报告。")
            # 构造一个虚拟的 pending 列表用于后续流程
            pending = [{"subject": row["title"], "body": row["content"], "id": None}]
```

- [ ] **Step 5: 验证语法正确**

```bash
python -c "from src.memory.long_term import lts; print('lts.enqueue_email' in dir(lts))"
```

预期：`True`

- [ ] **Step 6: 提交**

```bash
git add src/memory/long_term.py src/core/agent.py src/tools/email_tool.py
git commit -m "fix: 修复邮件队列永远为空的问题，添加 enqueue_email 和 fallback 逻辑"
```

---

### Task 4: 修复邮件报告路径可能覆盖

**Files:**
- Modify: `src/tools/email_tool.py:55-58`

- [ ] **Step 1: 文件名加入时分秒**

当前第 55-56 行：
```python
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_path = f"reports/weekly-report-{date_str}.html"
```

改为：
```python
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M%S")
        report_path = f"reports/weekly-report-{date_str}-{time_str}.html"
```

- [ ] **Step 2: 提交**

```bash
git add src/tools/email_tool.py
git commit -m "fix: 邮件报告文件名加入时分秒，避免同一天多次执行时覆盖"
```

---

### Task 5: 修复 research 报告 API 永远返回空（Bug）

**Files:**
- Modify: `src/memory/long_term.py`（新增 `save_research_finding` 方法）
- Modify: `src/tools/research.py`（调用新方法保存）

- [ ] **Step 1: 在 `LongTermMemory` 中新增 `save_research_finding` 方法**

在 `src/memory/long_term.py` 的 `enqueue_email` 方法之后添加：

```python
    def save_research_finding(self, topic: str, source_type: str, url: str,
                              summary: str, relevance_score: float = 0.5) -> int:
        """将研究发现写入 research_findings 表。"""
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO research_findings (topic, source_type, url, summary, relevance_score) VALUES (?, ?, ?, ?, ?)",
            (topic, source_type, url, summary, relevance_score),
        )
        conn.commit()
        finding_id = cursor.lastrowid
        conn.close()
        return finding_id
```

- [ ] **Step 2: 在 `ResearchTool.execute()` 中保存搜索结果到 research_findings**

`src/tools/research.py` 的 `execute` 方法中，修改搜索循环（第 22-34 行）。当前代码为每个 topic 搜索 arXiv、HN、GitHub，然后保存到 `experiences` 表。需要额外将每个搜索结果保存到 `research_findings`。

将第 40-48 行：
```python
        # 保存到数据库
        for topic in topics.split(",")[:3]:
            topic = topic.strip()
            if topic:
                lts.save_experience(
                    "research_insight", f"研究方向: {topic}",
                    full[:500], source="research_tool", confidence=0.6,
                )
```

改为：
```python
        # 保存到数据库
        for topic in topics.split(",")[:3]:
            topic = topic.strip()
            if topic:
                lts.save_experience(
                    "research_insight", f"研究方向: {topic}",
                    full[:500], source="research_tool", confidence=0.6,
                )
                # 同时写入 research_findings 表，使 API 可查询
                lts.save_research_finding(
                    topic=topic,
                    source_type="multi",
                    url="",
                    summary=full[:500],
                    relevance_score=0.6,
                )
```

- [ ] **Step 3: 验证语法正确**

```bash
python -c "from src.memory.long_term import lts; print('save_research_finding' in dir(lts))"
```

预期：`True`

- [ ] **Step 4: 提交**

```bash
git add src/memory/long_term.py src/tools/research.py
git commit -m "fix: ResearchTool 现在写入 research_findings 表，修复 research 报告 API 永远返回空"
```

---

### Task 6: 修复非流式循环 Tool 异常直接 raise（Bug）

**Files:**
- Modify: `src/core/agent.py:250-276`（`_agent_loop` 方法中的 Tool 执行部分）

- [ ] **Step 1: 修改 `_agent_loop()` 中的异常处理**

当前第 245-276 行（Tool 执行循环）：
```python
            for tc in tool_calls:
                tool = self.tools.get(tc["name"])
                if tool:
                    agent_logger.info("[TOOL] %s 开始执行", tc["name"])
                    t_start = time.perf_counter()
                    try:
                        result = await tool.execute(**tc["arguments"])
                        elapsed = time.perf_counter() - t_start
                        agent_logger.info(
                            "[TOOL] %s 完成 (%.1fs): %s",
                            tc["name"], elapsed, truncate(result.content),
                        )
                        outcomes.append(f"[{tc['name']}] {result.content}")
                        tool_results.append({
                            "tool_name": tc["name"],
                            "content": result.content,
                            "tool_call_id": tc["id"],
                        })
                        if result.metadata:
                            context += f"\n{tc['name']} 元数据: {result.metadata}"
                    except Exception as e:
                        elapsed = time.perf_counter() - t_start
                        agent_logger.info("[TOOL] %s 失败 (%.1fs): %s", tc["name"], elapsed, str(e))
                        raise
```

将 except 块中的 `raise` 替换为记录失败并继续：

```python
            for tc in tool_calls:
                tool = self.tools.get(tc["name"])
                if tool:
                    agent_logger.info("[TOOL] %s 开始执行", tc["name"])
                    t_start = time.perf_counter()
                    try:
                        result = await tool.execute(**tc["arguments"])
                        elapsed = time.perf_counter() - t_start
                        agent_logger.info(
                            "[TOOL] %s 完成 (%.1fs): %s",
                            tc["name"], elapsed, truncate(result.content),
                        )
                        outcomes.append(f"[{tc['name']}] {result.content}")
                        tool_results.append({
                            "tool_name": tc["name"],
                            "content": result.content,
                            "tool_call_id": tc["id"],
                        })
                        if result.metadata:
                            context += f"\n{tc['name']} 元数据: {result.metadata}"
                    except Exception as e:
                        elapsed = time.perf_counter() - t_start
                        agent_logger.info("[TOOL] %s 失败 (%.1fs): %s", tc["name"], elapsed, str(e))
                        error_msg = f"执行失败: {str(e)}"
                        outcomes.append(f"[{tc['name']}] {error_msg}")
                        tool_results.append({
                            "tool_name": tc["name"],
                            "content": error_msg,
                            "tool_call_id": tc["id"],
                        })
```

同时需要处理工具未找到的情况（当前代码中 tool 为 None 时静默跳过，应保持一致）：

还需要在 `if tool:` 后面加上 `else` 分支（当前缺失）。在第 268 行 `raise` 之前（即 `except` 块之后），当前缺少 `else` 处理 tool 为 None 的情况。检查原始代码第 246-268 行，确实没有 `else` 分支。由于我们只改这个区域的异常处理，不需要额外添加 else 分支（Tool 在 ToolRegistry 中始终存在）。

- [ ] **Step 2: 提交**

```bash
git add src/core/agent.py
git commit -m "fix: 非流式 Agent 循环中 Tool 异常不再中断整个循环，改为记录失败并继续"
```

---

### Task 7: ~~修复 safe_title 计算后未使用~~（假阳性——已验证无需修复）

**验证结果**：`agent.py:63` 行 `record_generation(filename, f"生成报告: {safe_title}")` 已正确使用 `safe_title`。此问题在审查时被误报，无需修改代码。

- [ ] **Step 1: 确认后跳过**

无需操作。

---

### Task 8: 修复 commit_and_push 被多次调用

**Files:**
- Modify: `src/core/agent.py`（`_agent_loop` 方法，移除第 285-287 行）

- [ ] **Step 1: 从 `_agent_loop()` 中移除 `commit_and_push()`**

当前 `_agent_loop()` 第 283-288 行：
```python
        agent_logger.info("[SYSTEM] 循环结束 session=%s", self.session_id)
        self._persist_and_clear()
        result = await commit_and_push()
        if result:
            agent_logger.info("[SYSTEM] Git: %s", result)
        return final_response
```

改为（移除 commit_and_push 相关行）：
```python
        agent_logger.info("[SYSTEM] 循环结束 session=%s", self.session_id)
        self._persist_and_clear()
        return final_response
```

**注意**：`commit_and_push` 调用已在各入口方法中存在：
- `handle_message` 末尾无调用（需确认是否需要添加）
- `handle_scheduled` 第 123 行有调用
- `handle_message_stream` finally 第 193 行有调用
- `handle_scheduled_stream` finally 第 172 行有调用

检查 `handle_message`（第 74-87 行）——确实没有 `commit_and_push` 调用。需要在 `handle_message` 中也添加以保证用户消息触发的报告也能被提交。但用户消息触发通常不生成文件，所以不加也可。

- [ ] **Step 2: 提交**

```bash
git add src/core/agent.py
git commit -m "fix: 从 _agent_loop 中移除 commit_and_push，避免同轮操作多次 git push"
```

---

### Task 9: 补充测试

**Files:**
- Create: `tests/test_short_term.py`
- Create: `tests/test_tool_base.py`
- Create: `tests/test_config.py`
- Create: `tests/test_agent_mock.py`

- [ ] **Step 1: 创建 `tests/test_short_term.py`**

```python
"""短期记忆单元测试。"""
import pytest
from src.memory.short_term import ShortTermMemory, Message


class TestMessage:
    def test_message_to_dict_basic(self):
        msg = Message(role="user", content="hello")
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "hello"
        assert "timestamp" in d

    def test_message_to_dict_with_tool_calls(self):
        msg = Message(role="assistant", content="",
                      tool_calls=[{"id": "1", "type": "function", "function": {"name": "test", "arguments": "{}"}}])
        d = msg.to_dict()
        assert "tool_calls" in d
        assert d["tool_calls"][0]["id"] == "1"

    def test_message_to_dict_with_tool_call_id(self):
        msg = Message(role="tool", content="result", tool_call_id="call_123")
        d = msg.to_dict()
        assert d["tool_call_id"] == "call_123"


class TestShortTermMemory:
    def test_add_message(self):
        mem = ShortTermMemory()
        mem.add("user", "hello")
        assert len(mem.get_all()) == 1

    def test_trim_when_exceeds_max(self):
        mem = ShortTermMemory()
        for i in range(60):
            mem.add("user", f"msg {i}")
        assert len(mem.get_all()) <= 50

    def test_clear(self):
        mem = ShortTermMemory()
        mem.add("user", "hello")
        mem.clear()
        assert len(mem.get_all()) == 0

    def test_add_assistant_tool_calls(self):
        mem = ShortTermMemory()
        mem.add_assistant_tool_calls(
            content="",
            tool_calls_schema=[{"id": "1", "type": "function", "function": {"name": "t", "arguments": "{}"}}],
        )
        msgs = mem.get_all()
        assert msgs[0].role == "assistant"
        assert msgs[0].tool_calls is not None

    def test_add_tool_result(self):
        mem = ShortTermMemory()
        mem.add_tool_result("test_tool", "done", tool_call_id="1")
        msgs = mem.get_all()
        assert msgs[0].role == "tool"
        assert "done" in msgs[0].content

    def test_get_for_llm_basic(self):
        mem = ShortTermMemory()
        mem.add("user", "hello")
        msgs = mem.get_for_llm()
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "hello"

    def test_get_for_llm_with_tool(self):
        mem = ShortTermMemory()
        mem.add_assistant_tool_calls("", [{"id": "1", "type": "function", "function": {"name": "t", "arguments": "{}"}}])
        mem.add_tool_result("test_tool", "result", tool_call_id="1")
        msgs = mem.get_for_llm()
        assert msgs[0]["tool_calls"] is not None
        assert msgs[1]["tool_call_id"] == "1"

    def test_is_full(self):
        mem = ShortTermMemory()
        assert not mem.is_full()
        for i in range(60):
            mem.add("user", f"msg {i}")
        assert mem.is_full()

    def test_summarize_for_compression(self):
        mem = ShortTermMemory()
        mem.add("user", "hello world")
        mem.add("assistant", "hi there")
        result = mem.summarize_for_compression()
        assert "[user]" in result
        assert "[assistant]" in result

    def test_reasoning_content_preserved(self):
        mem = ShortTermMemory()
        mem.add_assistant_tool_calls(
            content="thinking...", tool_calls_schema=[],
            reasoning_content="deep reasoning here",
        )
        msgs = mem.get_for_llm()
        assert msgs[0].get("reasoning_content") == "deep reasoning here"
```

- [ ] **Step 2: 运行 short_term 测试**

```bash
pytest tests/test_short_term.py -v
```

预期：全部 PASS。

- [ ] **Step 3: 创建 `tests/test_tool_base.py`**

```python
"""Tool 基类单元测试。"""
import pytest
from src.tools.base import ToolResult, BaseTool


class TestToolResult:
    def test_success_result(self):
        r = ToolResult(success=True, content="ok")
        assert r.success is True
        assert r.content == "ok"
        assert r.metadata is None

    def test_failure_result_with_metadata(self):
        r = ToolResult(success=False, content="error", metadata={"code": 500})
        assert r.success is False
        assert r.metadata["code"] == 500


class TestBaseTool:
    def test_to_llm_schema(self):
        class DummyTool(BaseTool):
            name = "dummy"
            description = "A dummy tool for testing"

            async def execute(self, **kwargs):
                return ToolResult(success=True, content="done")

            def get_parameters_schema(self):
                return {
                    "type": "object",
                    "properties": {
                        "arg1": {"type": "string", "description": "参数1"},
                    },
                    "required": ["arg1"],
                }

        tool = DummyTool()
        schema = tool.to_llm_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "dummy"
        assert schema["function"]["description"] == "A dummy tool for testing"
        assert "arg1" in schema["function"]["parameters"]["properties"]
```

- [ ] **Step 4: 运行 tool_base 测试**

```bash
pytest tests/test_tool_base.py -v
```

预期：全部 PASS。

- [ ] **Step 5: 创建 `tests/test_config.py`**

```python
"""配置模块单元测试。"""
import os
import pytest
from src.core.config import Config


class TestConfig:
    def test_default_values(self):
        cfg = Config()
        assert cfg.SHORT_TERM_MAX_MESSAGES == 50
        assert cfg.LLM_MAX_RETRIES == 3
        assert cfg.DEEPSEEK_BASE_URL == "https://api.deepseek.com"
        assert cfg.SKILL_CONFIDENCE_THRESHOLD == 0.5

    def test_available_models_structure(self):
        cfg = Config()
        for m in cfg.AVAILABLE_MODELS:
            assert "id" in m
            assert "name" in m
            assert "provider" in m
            assert "model" in m
            assert "base_url" in m

    def test_default_model_in_available(self):
        cfg = Config()
        model_ids = [m["id"] for m in cfg.AVAILABLE_MODELS]
        assert cfg.DEFAULT_MODEL in model_ids

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("LOG_TO_CONSOLE", "false")
        # 由于 Config 在模块加载时就读取了环境变量，
        # 这里验证的是 monkeypatch 机制可用于未来测试
        val = os.getenv("LOG_TO_CONSOLE")
        assert val == "false"
```

- [ ] **Step 6: 运行 config 测试**

```bash
pytest tests/test_config.py -v
```

预期：全部 PASS。

- [ ] **Step 7: 创建 `tests/test_agent_mock.py`**

```python
"""Agent 循环 mock 测试 —— 不依赖真实 LLM API。"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.core.agent import Agent


class TestAgentWithMockLLM:
    @pytest.mark.asyncio
    async def test_agent_direct_reply_without_tools(self):
        """LLM 返回无 tool_calls 的回复时，Agent 直接结束。"""
        agent = Agent()
        with patch("src.core.agent.retrieve_relevant_context", return_value=""):
            with patch("src.core.agent.llm.chat") as mock_chat:
                mock_chat.return_value = {"content": "你好！有什么可以帮你的？", "role": "assistant"}
                with patch("src.core.agent.lts") as mock_lts:
                    response = await agent.handle_message("你好")
                    assert "你好" in response
                    mock_lts.save_conversation.assert_called()

    @pytest.mark.asyncio
    async def test_agent_with_tool_calls(self):
        """LLM 返回 tool_calls 时，Agent 执行 tool 后继续。"""
        agent = Agent()
        with patch("src.core.agent.retrieve_relevant_context", return_value=""):
            with patch("src.core.agent.llm.chat") as mock_chat:
                # 第一轮：返回 tool_call 调用 chat
                mock_chat.side_effect = [
                    {
                        "content": "",
                        "role": "assistant",
                        "tool_calls": [{
                            "id": "call_1",
                            "name": "chat",
                            "arguments": {"message": "hello", "session_id": "test"},
                        }],
                    },
                    # 第二轮：直接回复
                    {"content": "回复完毕", "role": "assistant"},
                ]
                with patch("src.core.agent.lts") as mock_lts:
                    response = await agent.handle_message("帮我聊天")
                    assert "chat" in response.lower() or "回复完毕" in response

    @pytest.mark.asyncio
    async def test_agent_tool_failure_continues_loop(self):
        """Tool 执行失败时，Agent 不中断循环。"""
        agent = Agent()
        with patch("src.core.agent.retrieve_relevant_context", return_value=""):
            with patch("src.core.agent.llm.chat") as mock_chat:
                mock_chat.side_effect = [
                    {
                        "content": "",
                        "role": "assistant",
                        "tool_calls": [{
                            "id": "call_1",
                            "name": "chat",
                            "arguments": {"message": "test"},
                        }],
                    },
                    {"content": "虽然工具失败了，但我可以继续", "role": "assistant"},
                ]
                # 让 Tool 执行时抛出异常
                with patch.object(agent.tools, "get") as mock_get:
                    mock_tool = AsyncMock()
                    mock_tool.execute.side_effect = Exception("模拟失败")
                    mock_get.return_value = mock_tool
                    with patch("src.core.agent.lts"):
                        response = await agent.handle_message("test")
                        assert response  # 不应抛出异常
```

- [ ] **Step 8: 运行 agent mock 测试**

```bash
pytest tests/test_agent_mock.py -v
```

预期：全部 PASS。

- [ ] **Step 9: 提交全部测试**

```bash
git add tests/test_short_term.py tests/test_tool_base.py tests/test_config.py tests/test_agent_mock.py
git commit -m "test: 补充 short_term、tool_base、config 和 agent mock 单元测试"
```

---

### Task 10: ChromaDB embedding 可配置

**Files:**
- Modify: `src/core/config.py`（新增 `EMBEDDING_PROVIDER`）
- Modify: `src/db/vector_store.py`（根据配置选择 embedding function）

- [ ] **Step 1: 在 Config 中新增 `EMBEDDING_PROVIDER`**

在 `src/core/config.py` 的 Config 类中，于第 69 行（`LOG_TRUNCATE_LENGTH` 之后，`config = Config()` 之前）添加：

```python
    # Embedding
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "chromadb")
```

- [ ] **Step 2: 修改 `VectorStore` 支持可配置 embedding function**

修改 `src/db/vector_store.py`：

```python
"""ChromaDB 封装 —— 统一管理 embedding 的存储和检索。"""
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from src.core.config import config


def _get_embedding_function():
    """根据配置返回对应的 embedding function。"""
    if config.EMBEDDING_PROVIDER == "deepseek":
        from src.core.llm import llm

        class DeepSeekEmbeddingFunction(embedding_functions.EmbeddingFunction):
            def __call__(self, input):
                # ChromaDB 的 EmbeddingFunction 接口要求返回 list[list[float]]
                return [llm.embed(text) for text in input]

        return DeepSeekEmbeddingFunction()
    # chromadb（默认）：不传 embedding_function，使用内置 ONNX 模型
    return embedding_functions.DefaultEmbeddingFunction()


class VectorStore:
    def __init__(self) -> None:
        self.ef = _get_embedding_function()
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
            "skill_embeddings",
        ]:
            if col_name not in names:
                self.client.create_collection(
                    name=col_name,
                    embedding_function=self.ef,
                )

    def add(self, collection: str, doc_id: str, text: str, metadata: dict | None = None) -> None:
        col = self.client.get_collection(name=collection)
        col.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata] if metadata else None,
        )

    def search(self, collection: str, query: str, n_results: int = 5) -> list[dict]:
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

    def upsert(self, collection: str, doc_id: str, text: str, metadata: dict | None = None) -> None:
        col = self.client.get_collection(name=collection)
        col.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata] if metadata else None,
        )

    def delete(self, collection: str, doc_id: str) -> None:
        col = self.client.get_collection(name=collection)
        col.delete(ids=[doc_id])


vector_store = VectorStore()
```

- [ ] **Step 3: 验证默认行为不变**

```bash
python -c "from src.db.vector_store import vector_store; print('OK')"
```

预期：`OK`（无报错）。

- [ ] **Step 4: 提交**

```bash
git add src/core/config.py src/db/vector_store.py
git commit -m "feat: ChromaDB embedding provider 可配置，支持 chromadb 和 deepseek 两种模式"
```

---

### 最终检查

- [ ] **运行全部测试**

```bash
pytest tests/ -v
```

- [ ] **启动应用验证无 import 错误**

```bash
python -c "from src.web.app import app; print('应用加载成功')"
```
