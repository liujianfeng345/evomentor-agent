# 代码质量全面改进 — 设计文档

**日期**: 2026-05-24
**状态**: 待实施

## 概述

对 Evomentor 项目进行全面的代码质量审查，修复 3 个严重 Bug、5 个代码质量问题、3 个优化项。

---

## 第一组：数据流修复

### 1. 邮件队列永远为空（Bug）

**现象**：`EmailTool` 从 `pending_emails` 表读取待发邮件，但代码库中没有任何地方向该表写入数据。结果是每次调用 send_email 都返回"没有待发送的邮件"。

**根因**：`pending_emails` 表只有消费者（EmailTool.read）没有生产者（写入入口）。

**修复**：
- 在 `LongTermMemory` 中新增 `enqueue_email(subject: str, body: str) -> int` 方法
- 在 `handle_scheduled()` 中，保存报告后自动调用 `lts.enqueue_email()` 将摘要入队
- 在 `handle_scheduled_stream()` 同样处理
- 修改 `EmailTool.execute()`：当队列为空时，从 `agent_reports` 表取最新一条报告作为 fallback 内容
- 涉及文件：`src/memory/long_term.py`、`src/core/agent.py`、`src/tools/email_tool.py`

**验收标准**：
- `lts.enqueue_email()` 能正确写入 pending_emails 表
- `handle_scheduled("periodic_check")` 执行后，pending_emails 表中有新记录
- 手动调用 `/api/emails/send` 能成功发送邮件

### 2. research 报告 API 永远返回空（Bug）

**现象**：`/api/reports?type=research` 查询 `research_findings` 表，但 `ResearchTool` 只写 `experiences` 表，从来不动 `research_findings`。

**根因**：`ResearchTool.execute()` 缺少写入 `research_findings` 的逻辑。

**修复**：
- 在 `LongTermMemory` 中新增 `save_research_finding(topic, source_type, url, summary, relevance_score) -> int` 方法
- 在 `ResearchTool.execute()` 中，每个 topic 搜索完成后调用该方法保存
- 涉及文件：`src/memory/long_term.py`、`src/tools/research.py`

**验收标准**：
- `ResearchTool` 执行后，`research_findings` 表有新记录
- `GET /api/reports?type=research` 能返回数据

---

## 第二组：代码质量修复

### 3. 非流式循环 Tool 异常直接 raise（Bug）

**现象**：`agent.py` 的 `_agent_loop()` 中第 268 行 `raise` 直接中断循环，而流式版本 `_agent_loop_stream()` 已正确处理异常。

**修复**：
- 将 `raise` 替换为捕获后记录 tool result（`success=False`），继续循环
- 具体：在 except 块中构造失败的 tool_result 并追加到 tool_results 列表，移除 `raise`
- 涉及文件：`src/core/agent.py`（`_agent_loop` 方法，约第 265-268 行）

**验收标准**：
- 一个 Tool 失败时，Agent 循环能继续执行后续轮次
- 失败的 Tool 有对应日志记录

### 4. ~~safe_title 计算后未使用~~（假阳性——已验证无需修复）

**验证结果**：`agent.py:63` 行 `record_generation(filename, f"生成报告: {safe_title}")` 已正确使用 `safe_title`。审查时误判，实际代码无误。

### 5. 循环导入 hack

**现象**：`scheduler/jobs.py` 和 `memory/retrieval.py` 使用 `__import__("src.db.models", fromlist=["get_connection"]).get_connection()` 规避循环导入。

**修复**：
- 将 `get_connection()` 从 `src/db/models.py` 抽取到新文件 `src/db/connection.py`
- `src/db/models.py` 从 `src/db/connection` 重新导出以保持向后兼容
- `scheduler/jobs.py` 和 `retrieval.py` 改为直接 `from src.db.connection import get_connection`
- 涉及文件：新建 `src/db/connection.py`，修改 `src/db/models.py`、`src/scheduler/jobs.py`、`src/memory/retrieval.py`

**验收标准**：
- 所有 `__import__` hack 被移除
- 现有功能不受影响

### 6. commit_and_push 被多次调用

**现象**：`_agent_loop()` 末尾、`handle_scheduled()` 末尾、流式方法 finally 中均调用 `commit_and_push()`。一次调度触发可能产生多次 git push。

**修复**：
- 从 `_agent_loop()` 中移除 `commit_and_push()` 调用
- 只在各入口方法（`handle_message` / `handle_scheduled` / `handle_message_stream` / `handle_scheduled_stream`）调用一次
- 涉及文件：`src/core/agent.py`

**验收标准**：
- 一次 `handle_scheduled()` 调用只产生一次 git push

### 7. email_tool.py 重复动态 import

**现象**：文件顶部已 `from datetime import datetime`，但第 63 行又用 `__import__('datetime').datetime.now()`。

**修复**：将第 63 行的 `__import__('datetime').datetime.now().strftime(...)` 改为 `datetime.now().strftime(...)`。
- 涉及文件：`src/tools/email_tool.py`

---

## 第三组：优化增强

### 8. 测试覆盖率补充

**现状**：`tests/` 下只有 5 个测试文件，`test_agent.py` 仅 2 个测试且全依赖真实 API。

**新增测试文件**：

| 文件 | 测试内容 |
|------|----------|
| `tests/test_short_term.py` | 消息添加/删除、容量裁剪、`get_for_llm()` 序列化、`summarize_for_compression()` |
| `tests/test_tool_base.py` | `ToolResult` 数据类、`BaseTool.to_llm_schema()` |
| `tests/test_config.py` | 默认值验证、环境变量覆盖 |
| `tests/test_agent_mock.py` | mock LLM 的 Agent 循环、tool_calls 处理、无 tool 直接回复 |

### 9. ChromaDB embedding 可配置

**现象**：ChromaDB 内置 embedding 对中文支持不佳。

**修复**：
- 在 `Config` 中新增 `EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "chromadb")`
- 选项：`chromadb`（默认，内置函数）/ `deepseek`（调用 LLMClient.embed()）
- `VectorStore.__init__()` 根据配置选择 embedding function
- 涉及文件：`src/core/config.py`、`src/db/vector_store.py`

**验收标准**：
- 默认行为不变（使用 ChromaDB 内置 embedding）
- 设置 `EMBEDDING_PROVIDER=deepseek` 后使用 DeepSeek embedding

### 10. 邮件报告路径可能覆盖

**现象**：`email_tool.py` 用 `weekly-report-{date}.html` 命名，同一天多次执行会覆盖。

**修复**：文件名改为 `weekly-report-{date}-{HHMMSS}.html`。
- 涉及文件：`src/tools/email_tool.py`

---

## 影响范围汇总

| 文件 | 变更类型 |
|------|----------|
| `src/memory/long_term.py` | 新增 `enqueue_email()`、`save_research_finding()` |
| `src/core/agent.py` | 修复异常处理、移除重复 `commit_and_push`、修复 `safe_title`、添加邮件入队 |
| `src/tools/email_tool.py` | fallback 逻辑、文件名时间戳、清理重复 import |
| `src/tools/research.py` | 写入 `research_findings` |
| `src/db/connection.py` | **新建**，抽取 `get_connection()` |
| `src/db/models.py` | 移除 `get_connection()`，从 `connection.py` 重导出 |
| `src/scheduler/jobs.py` | 改用直接 import |
| `src/memory/retrieval.py` | 改用直接 import |
| `src/core/config.py` | 新增 `EMBEDDING_PROVIDER` |
| `src/db/vector_store.py` | 支持可配置 embedding function |
| `tests/test_short_term.py` | **新建** |
| `tests/test_tool_base.py` | **新建** |
| `tests/test_config.py` | **新建** |
| `tests/test_agent_mock.py` | **新建** |

## 不涉及的部分

- 前端（`src/web/templates/`、`src/web/static/`）
- Skill 文件（`skills/` 目录）
- 报告文件（`reports/` 目录）
- 调度器业务逻辑变更
