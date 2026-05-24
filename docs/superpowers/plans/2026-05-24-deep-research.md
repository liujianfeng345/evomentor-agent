# 深度研究报告功能 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建可配置深度的多主题研究报告生成系统，支持定时/手动触发，报告以 Markdown 文件存档并自动发送邮件。

**Architecture:** 新增 ResearchManager 服务类作为核心研究管道，独立于 Agent 循环管理多轮搜索与分析；通过 DeepResearchTool 桥接到 Agent 工具系统；定时任务直接调用 Manager，手动触发通过 SSE 流式 API 或 Agent 对话。

**Tech Stack:** Python (asyncio), SQLite, FastAPI (SSE), APScheduler, DeepSeek API (LLM)

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/research/__init__.py` | 新建 | 模块入口，导出 ResearchManager |
| `src/research/manager.py` | 新建 | 研究管道核心：多轮搜索→分析→报告 |
| `src/tools/deep_research.py` | 新建 | DeepResearchTool，Agent 可调用封装 |
| `src/db/models.py` | 修改 | SCHEMA 新增 research_topics 表 |
| `src/tools/__init__.py` | 修改 | 注册 deep_research 工具 |
| `src/core/agent.py` | 修改 | SYSTEM_PROMPT + SCHEDULED_PROMPTS 添加条目 |
| `src/scheduler/jobs.py` | 修改 | 新增 scheduled_research 定时任务 |
| `src/web/routes.py` | 修改 | 新增主题 CRUD + 研究触发 API |
| `tests/test_research_manager.py` | 新建 | ResearchManager 单元测试 |
| `tests/test_research_api.py` | 新建 | API 端点集成测试 |

---

### Task 1: 添加 research_topics 表

**Files:**
- Modify: `src/db/models.py:93-94`（在 `agent_reports` 表定义后插入）

- [ ] **Step 1: 在 SCHEMA 中添加 research_topics 表定义**

在 `agent_reports` 的 CREATE TABLE 之后、`"""` 结束之前，插入：

```sql
CREATE TABLE IF NOT EXISTS research_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    depth TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

编辑位置为 `src/db/models.py` 第 93 行 `);` 之后、第 94 行 `"""` 之前。

- [ ] **Step 2: 验证数据库初始化**

```bash
python -c "from src.db.models import init_db; init_db(); print('OK')"
```

Expected: `OK`（无异常）

- [ ] **Step 3: 验证表已创建**

```bash
python -c "from src.db.models import get_connection; conn=get_connection(); rows=conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='research_topics'\").fetchall(); conn.close(); print(rows)"
```

Expected: `[<sqlite3.Row object at ...>]`（表存在）

- [ ] **Step 4: Commit**

```bash
git add src/db/models.py
git commit -m "feat: 添加 research_topics 表定义"
```

---

### Task 2: 创建 ResearchManager 核心

**Files:**
- Create: `src/research/__init__.py`
- Create: `src/research/manager.py`

- [ ] **Step 1: 创建模块入口文件**

```python
# src/research/__init__.py
"""研究报告生成模块。"""
from src.research.manager import ResearchManager  # noqa: F401
```

- [ ] **Step 2: 编写 ResearchManager 完整实现**

```python
# src/research/manager.py
"""ResearchManager —— 多轮深度研究管道，独立于 Agent 循环运行。"""
import asyncio
import os
import re
from datetime import datetime
from src.core.llm import llm
from src.core.git_auto import record_generation
from src.memory.long_term import lts
from src.db.models import get_connection
from src.tools.research import ResearchTool
from src.tools.web_search import WebSearchTool
from src.core.logger import get_logger

research_logger = get_logger("research")

# 深度模式对应的最大搜索轮数
DEPTH_ROUNDS = {"quick": 1, "standard": 2, "deep": 3}


def _slugify(text: str) -> str:
    """将主题名转为安全的文件名片段。"""
    slug = re.sub(r"[^\w一-鿿\-]", "_", text.strip())
    return slug[:60].strip("_")


class ResearchManager:
    """研究报告生成管理器。

    独立于 Agent 循环，直接调用搜索工具和 LLM，控制多轮迭代深度。
    支持两种调用方式：
    - run_all / run_single: 非流式，用于定时任务
    - run_all_stream: 流式 async generator，用于 SSE API
    """

    def __init__(self) -> None:
        self.research_tool = ResearchTool()
        self.web_search_tool = WebSearchTool()

    # ── 数据库读取 ──────────────────────────────────────

    def _get_topics(self, topic_ids: list[int] | None = None) -> list[dict]:
        """从 DB 读取活跃主题列表。"""
        conn = get_connection()
        if topic_ids:
            placeholders = ",".join("?" * len(topic_ids))
            rows = conn.execute(
                f"SELECT * FROM research_topics "
                f"WHERE id IN ({placeholders}) AND status = 'active'",
                topic_ids,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM research_topics WHERE status = 'active'"
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def _get_topic_by_id(self, topic_id: int) -> dict | None:
        """按 ID 读取单个主题。"""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM research_topics WHERE id = ?", (topic_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    # ── 批量入口 ────────────────────────────────────────

    async def run_all(
        self, topic_ids: list[int] | None = None, model_id: str = ""
    ) -> list[str]:
        """批量执行：逐主题串行生成报告，返回报告文件路径列表。"""
        topics = self._get_topics(topic_ids)
        if not topics:
            research_logger.info("[RESEARCH] 无活跃主题，跳过")
            return []
        reports: list[str] = []
        for topic in topics:
            try:
                path = await self.run_single(topic["id"], model_id)
                reports.append(path)
            except Exception as e:
                research_logger.error(
                    "[RESEARCH] 主题 [%s] 研究失败: %s", topic["name"], str(e)
                )
        return reports

    async def run_all_stream(
        self, topic_ids: list[int] | None = None, model_id: str = ""
    ):
        """流式批量执行，yield SSE 事件 dict。"""
        topics = self._get_topics(topic_ids)
        yield {
            "type": "research_start",
            "topics": [t["name"] for t in topics],
            "total": len(topics),
        }
        for topic in topics:
            yield {
                "type": "topic_start",
                "topic": topic["name"],
                "depth": topic["depth"],
            }
            try:
                async for event in self._research_pipeline_stream(topic, model_id):
                    yield event
            except Exception as e:
                yield {
                    "type": "error",
                    "message": f"主题 [{topic['name']}] 研究失败: {str(e)}",
                }
        yield {"type": "research_done"}

    async def run_single(self, topic_id: int, model_id: str = "") -> str:
        """单主题研究管道，返回报告文件路径。"""
        topic = self._get_topic_by_id(topic_id)
        if not topic:
            raise ValueError(f"主题不存在: {topic_id}")
        md_content = await self._research_pipeline(topic, model_id)
        return self._save_and_enqueue(topic["name"], md_content)

    # ── 核心管道（非流式）────────────────────────────────

    async def _research_pipeline(self, topic: dict, model_id: str = "") -> str:
        """核心管道：多轮搜索 → 分析 → 报告生成。返回 Markdown 文本。"""
        topic_name = topic["name"]
        description = topic.get("description", "")
        depth = topic.get("depth", "standard")
        max_rounds = DEPTH_ROUNDS.get(depth, 2)

        all_findings: list[str] = []
        next_context = topic_name
        if description:
            next_context = f"{topic_name}（{description}）"

        for round_num in range(1, max_rounds + 1):
            research_logger.info(
                "[RESEARCH] [%s] 第 %d/%d 轮搜索", topic_name, round_num, max_rounds
            )
            findings = await self._search_round(topic_name, next_context)
            all_findings.append(f"## 第 {round_num} 轮搜索发现\n\n{findings}")

            if round_num < max_rounds:
                analysis = await self._analyze(
                    topic_name, findings, round_num, depth
                )
                if not analysis.get("continue", True):
                    break
                gaps = analysis.get("gaps", "")
                if gaps:
                    next_context = gaps
                    all_findings.append(
                        f"## 第 {round_num} 轮分析\n\n"
                        f"**知识缺口**: {gaps}\n"
                        f"**阶段总结**: {analysis.get('summary', '')}"
                    )

        research_logger.info("[RESEARCH] [%s] 生成报告", topic_name)
        return await self._generate_report(topic_name, "\n\n".join(all_findings))

    # ── 核心管道（流式）──────────────────────────────────

    async def _research_pipeline_stream(self, topic: dict, model_id: str = ""):
        """流式版核心管道，yield SSE 事件 dict。"""
        topic_name = topic["name"]
        description = topic.get("description", "")
        depth = topic.get("depth", "standard")
        max_rounds = DEPTH_ROUNDS.get(depth, 2)

        all_findings: list[str] = []
        next_context = topic_name
        if description:
            next_context = f"{topic_name}（{description}）"

        for round_num in range(1, max_rounds + 1):
            yield {
                "type": "search_round",
                "round": round_num,
                "max_rounds": max_rounds,
                "topic": topic_name,
            }
            findings = await self._search_round(topic_name, next_context)
            yield {
                "type": "search_done",
                "round": round_num,
                "findings_length": len(findings),
            }
            all_findings.append(f"## 第 {round_num} 轮搜索发现\n\n{findings}")

            if round_num < max_rounds:
                analysis = await self._analyze(
                    topic_name, findings, round_num, depth
                )
                yield {
                    "type": "analysis",
                    "round": round_num,
                    "gaps": analysis.get("gaps", ""),
                    "summary": analysis.get("summary", ""),
                }
                if not analysis.get("continue", True):
                    break
                gaps = analysis.get("gaps", "")
                if gaps:
                    next_context = gaps
                    all_findings.append(
                        f"## 第 {round_num} 轮分析\n\n"
                        f"**知识缺口**: {gaps}\n"
                        f"**阶段总结**: {analysis.get('summary', '')}"
                    )

        yield {"type": "report_generating", "topic": topic_name}
        report = await self._generate_report(topic_name, "\n\n".join(all_findings))
        file_path = self._save_and_enqueue(topic_name, report)
        yield {"type": "report_done", "topic": topic_name, "file": file_path}

    # ── 搜索轮次 ────────────────────────────────────────

    async def _search_round(self, topic: str, context: str) -> str:
        """单轮多源并行搜索。返回合并后的发现文本。"""
        results = await asyncio.gather(
            self.research_tool.execute(topics=topic),
            self.web_search_tool.execute(
                query=f"{context} latest developments 2025 2026"
            ),
            return_exceptions=True,
        )

        parts: list[str] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                research_logger.warning(
                    "[RESEARCH] 搜索源 %d 失败: %s", i, str(result)
                )
                continue
            if hasattr(result, "success") and result.success and result.content:
                parts.append(result.content)
            elif hasattr(result, "content") and result.content:
                parts.append(result.content)

        return "\n\n".join(parts) if parts else "未获取到相关信息。"

    # ── LLM 分析 ────────────────────────────────────────

    async def _analyze(
        self, topic: str, findings: str, round_num: int, depth: str
    ) -> dict:
        """LLM 分析本轮发现，判断是否继续深入。

        Returns:
            {"continue": bool, "gaps": str, "summary": str}
        """
        prompt = f"""你是一位资深研究分析师。正在对主题「{topic}」进行第 {round_num} 轮研究分析。

当前研究深度模式: {depth}

本轮搜索发现:
{findings[:4000]}

请分析以上发现并返回 JSON 格式的判断：
1. 是否还有重要的知识缺口需要继续深入研究？(continue: true/false)
2. 如果有缺口，具体是什么？(gaps: 下一轮应该搜索的关键方向或具体问题)
3. 本轮的阶段总结 (summary: 本轮的核心发现，2-3句话)

仅返回 JSON，不要其他内容：
{{"continue": true/false, "gaps": "...", "summary": "..."}}"""

        try:
            response = llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            content = response.get("content", "{}")
            # 提取 JSON（LLM 可能在前后加了说明文字）
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                import json
                return json.loads(json_match.group())
            return {"continue": False, "gaps": "", "summary": content[:200]}
        except Exception as e:
            research_logger.warning("[RESEARCH] 分析失败: %s", str(e))
            return {"continue": False, "gaps": "", "summary": findings[:200]}

    # ── 报告生成 ────────────────────────────────────────

    async def _generate_report(self, topic: str, all_findings: str) -> str:
        """LLM 汇总所有轮次发现，生成结构化 Markdown 报告。"""
        prompt = f"""你是一位资深研究分析师。请根据以下所有研究发现，为「{topic}」生成一份结构化的研究报告。

所有研究发现:
{all_findings[:8000]}

报告格式要求（Markdown）：
# {topic} 研究报告

## 1. 概述
（2-3 句话概括本主题的研究现状和核心结论）

## 2. 核心发现
（列出 3-5 条最重要的发现，每条包含简短说明）

## 3. 关键项目/论文
（列出重要的开源项目或学术论文，包含名称、简介和链接）

## 4. 技术趋势
（分析该领域的技术发展趋势和方向）

## 5. 参考来源
（汇总所有引用的信息源链接）

要求：
- 内容详实，有具体数据和链接
- 中文撰写，专业术语保留英文
- Markdown 格式，层级清晰"""

        try:
            response = llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return response.get("content", f"# {topic} 研究报告\n\n报告生成失败，请重试。")
        except Exception as e:
            research_logger.error("[RESEARCH] 报告生成失败: %s", str(e))
            return f"# {topic} 研究报告\n\n报告生成失败: {e}"

    # ── 保存与通知 ──────────────────────────────────────

    def _save_and_enqueue(self, topic_name: str, md_content: str) -> str:
        """保存 Markdown 文件 + 入邮件队列 + 登记 Git 提交。

        Returns:
            报告文件路径
        """
        os.makedirs("reports", exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        slug = _slugify(topic_name)
        filename = f"reports/research-{slug}-{date_str}.md"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(md_content)

        # 登记 Git 自动提交
        record_generation(filename, f"研究报告: {topic_name}")

        # 存入 agent_reports 表
        title = md_content.strip().split("\n")[0].lstrip("#").strip()[:80]
        lts.save_agent_report(
            trigger="scheduled_research",
            title=f"[研究] {title}",
            content=md_content,
            session_id=f"research-{slug}-{date_str}",
        )

        # 将 Markdown 内容入邮件队列（EmailTool 发送时 LLM 转 HTML）
        lts.enqueue_email(
            subject=f"研究报告: {topic_name} — {date_str}",
            body=md_content,
        )

        research_logger.info("[RESEARCH] 报告已保存: %s", filename)
        return filename
```

- [ ] **Step 3: 验证模块可导入**

```bash
python -c "from src.research.manager import ResearchManager; m = ResearchManager(); print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/research/__init__.py src/research/manager.py
git commit -m "feat: 添加 ResearchManager 核心研究管道"
```

---

### Task 3: 创建 DeepResearchTool

**Files:**
- Create: `src/tools/deep_research.py`

- [ ] **Step 1: 编写 DeepResearchTool**

```python
# src/tools/deep_research.py
"""深度研究工具 —— Agent 可调用此工具对指定主题进行深度研究。"""
from src.tools.base import BaseTool, ToolResult
from src.research.manager import ResearchManager
from src.memory.long_term import lts


class DeepResearchTool(BaseTool):
    name = "deep_research"
    description = (
        "对指定主题进行深度研究，搜索论文、GitHub、网络等多种信息源，"
        "经过多轮迭代分析后生成结构化的研究报告。"
        "适合用户说「帮我研究 XX」「调查一下 XX 的最新进展」等场景。"
    )

    async def execute(self, topics: str = "", depth: str = "standard") -> ToolResult:
        """执行深度研究。

        Args:
            topics: 研究主题，逗号分隔。留空则使用 DB 中所有活跃主题。
            depth: 研究深度，quick/standard/deep，默认 standard。
        """
        valid_depths = {"quick", "standard", "deep"}
        if depth not in valid_depths:
            depth = "standard"

        manager = ResearchManager()

        if topics.strip():
            # 指定了主题：直接用临时主题执行研究，不走 DB
            topic_list = [t.strip() for t in topics.split(",") if t.strip()]
            reports: list[str] = []
            for t in topic_list:
                # 构造临时主题 dict
                topic = {"name": t, "description": "", "depth": depth}
                try:
                    from src.core.llm import llm as llm_client
                    md_content = await manager._research_pipeline(topic)
                    path = manager._save_and_enqueue(t["name"], md_content)
                    reports.append(path)
                except Exception as e:
                    return ToolResult(
                        success=False,
                        content=f"主题「{t}」研究失败: {str(e)}",
                    )
            return ToolResult(
                success=True,
                content=f"已完成 {len(reports)} 个主题的研究，报告已保存。\n\n"
                + "\n".join(f"- {r}" for r in reports),
            )
        else:
            # 未指定主题：从 DB 读取活跃主题
            report_paths = await manager.run_all()
            if not report_paths:
                return ToolResult(
                    success=True,
                    content="当前没有活跃的研究主题。请在研究主题管理中先添加主题。",
                )
            return ToolResult(
                success=True,
                content=f"已完成 {len(report_paths)} 个主题的研究，报告已保存。\n\n"
                + "\n".join(f"- {r}" for r in report_paths),
            )

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "topics": {
                    "type": "string",
                    "description": "研究主题，逗号分隔多个主题。留空则使用数据库中所有活跃的研究主题。",
                },
                "depth": {
                    "type": "string",
                    "enum": ["quick", "standard", "deep"],
                    "description": "研究深度: quick=快速(1轮搜索), standard=标准(2轮迭代), deep=深度(3轮迭代)。默认 standard。",
                },
            },
        }
```

- [ ] **Step 2: 验证工具可导入**

```bash
python -c "from src.tools.deep_research import DeepResearchTool; t = DeepResearchTool(); print(t.name, t.description[:30])"
```

Expected: `deep_research 对指定主题进行深度研究`

- [ ] **Step 3: Commit**

```bash
git add src/tools/deep_research.py
git commit -m "feat: 添加 DeepResearchTool，Agent 可调用的深度研究工具"
```

---

### Task 4: 注册工具并更新 Agent 提示词

**Files:**
- Modify: `src/tools/__init__.py`
- Modify: `src/core/agent.py`

- [ ] **Step 1: 在 ToolRegistry 中注册 deep_research**

编辑 `src/tools/__init__.py`，在导入区域添加 `from src.tools.deep_research import DeepResearchTool`（第 7 行附近），在 `self.tools` 字典中添加 `"deep_research": DeepResearchTool(),`。

修改后的文件：

```python
"""工具注册表 —— 集中管理所有 Tool 实例，提供 schema 列表给 Agent。"""
from src.tools.chat import ChatTool
from src.tools.github import GitHubTool
from src.tools.email_tool import EmailTool
from src.tools.research import ResearchTool
from src.tools.reflect import ReflectTool
from src.tools.skill_manager import SkillManagerTool
from src.tools.web_search import WebSearchTool
from src.tools.deep_research import DeepResearchTool


class ToolRegistry:
    def __init__(self, memory) -> None:
        self.tools: dict[str, object] = {
            "chat": ChatTool(memory),
            "github_analyze": GitHubTool(),
            "send_email": EmailTool(),
            "research": ResearchTool(),
            "reflect": ReflectTool(memory),
            "skill_manager": SkillManagerTool(),
            "web_search": WebSearchTool(),
            "deep_research": DeepResearchTool(),
        }

    def get_schemas(self) -> list[dict]:
        return [tool.to_llm_schema() for tool in self.tools.values()]

    def get(self, name: str):
        return self.tools.get(name)

    def list_names(self) -> list[str]:
        return list(self.tools.keys())
```

- [ ] **Step 2: 更新 SYSTEM_PROMPT**

编辑 `src/core/agent.py`，在 SYSTEM_PROMPT 的工具列表末尾（`- **web_search**: ...` 之后）添加：

```python
- **deep_research**: 对指定主题进行多源深度研究，支持多轮迭代，自动生成结构化研究报告。适合用户说「帮我研究 XX」「调查 XX 最新进展」时调用。
```

- [ ] **Step 3: 添加 SCHEDULED_PROMPTS 条目**

编辑 `src/core/agent.py`，在 SCHEDULED_PROMPTS 字典末尾添加：

```python
"scheduled_research": "现在需要为所有活跃的研究主题生成深度研究报告。请调用 deep_research 工具，不传 topics 参数以处理数据库中所有活跃主题。研究完成后，调用 send_email 工具发送报告邮件。",
```

- [ ] **Step 4: 验证 Agent 可正常初始化**

```bash
python -c "from src.core.agent import Agent; a = Agent(); print(len(a.tools.tools), 'tools'); print('OK')"
```

Expected: `8 tools` 后跟 `OK`

- [ ] **Step 5: Commit**

```bash
git add src/tools/__init__.py src/core/agent.py
git commit -m "feat: 注册 DeepResearchTool 并更新 Agent 提示词"
```

---

### Task 5: 添加定时研究任务

**Files:**
- Modify: `src/scheduler/jobs.py`

- [ ] **Step 1: 添加 scheduled_research 函数和调度注册**

编辑 `src/scheduler/jobs.py`：

在文件顶部导入区域添加 `from src.research.manager import ResearchManager`。

在 `send_daily_email` 函数之后、`start_scheduler` 函数之前添加：

```python
async def scheduled_research() -> None:
    """定时研究任务：为所有活跃主题生成研究报告并发送邮件。"""
    manager = ResearchManager()
    reports = await manager.run_all()
    if reports:
        # 所有主题报告已入邮件队列，触发发送
        from src.tools.email_tool import EmailTool
        email_tool = EmailTool()
        result = await email_tool.execute()
        research_logger.info(
            "[SCHEDULED] 研究完成: %d 篇报告, 邮件: %s",
            len(reports), result.content,
        )
```

在 `start_scheduler` 函数中，`daily_reflect` 注册之后、`scheduler.start()` 之前添加：

```python
# 每天定时研究报告（间隔24小时）
scheduler.add_job(
    scheduled_research,
    IntervalTrigger(hours=config.RESEARCH_SCHEDULE_HOURS),
    id="scheduled_research",
    name="定时研究报告",
    replace_existing=True,
)
```

同时需要在 `jobs.py` 顶部获取 logger：

```python
from src.core.logger import get_logger
research_logger = get_logger("research")
```

- [ ] **Step 2: 添加配置项**

编辑 `src/core/config.py`，在 `# 调度` 区域添加：

```python
RESEARCH_SCHEDULE_HOURS: int = int(os.getenv("RESEARCH_SCHEDULE_HOURS", "24"))
```

- [ ] **Step 3: 验证调度器可正常启动（不实际等待）**

```bash
python -c "from src.scheduler.jobs import start_scheduler, scheduled_research; print('调度器模块导入成功'); print('OK')"
```

Expected: `调度器模块导入成功` 后跟 `OK`

- [ ] **Step 4: Commit**

```bash
git add src/scheduler/jobs.py src/core/config.py
git commit -m "feat: 添加定时研究报告任务，默认每24小时执行"
```

---

### Task 6: 添加 API 端点

**Files:**
- Modify: `src/web/routes.py`

- [ ] **Step 1: 添加主题 CRUD 端点**

在 `src/web/routes.py` 中，`# ─── 操作列表` 区域之前，添加以下代码。

需要新增两个 Pydantic 模型（在 ChatRequest 等类定义附近添加）：

```python
class TopicCreate(BaseModel):
    name: str
    description: str = ""
    depth: str = "standard"


class TopicUpdate(BaseModel):
    name: str = ""
    description: str = ""
    depth: str = ""
    status: str = ""


class ResearchRequest(BaseModel):
    topic_ids: list[int] = []
    model: str = ""
```

然后在 `# ─── 操作列表` 之前添加以下端点：

```python
# ─── 研究主题管理 ─────────────────────────────────────────

@router.get("/api/research/topics")
async def list_research_topics():
    """获取所有研究主题。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM research_topics ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows]}


@router.post("/api/research/topics")
async def create_research_topic(req: TopicCreate):
    """新增研究主题。"""
    if not req.name.strip():
        return JSONResponse({"error": "主题名称不能为空"}, status_code=400)
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO research_topics (name, description, depth) VALUES (?, ?, ?)",
            (req.name.strip(), req.description.strip(), req.depth),
        )
        conn.commit()
        topic_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM research_topics WHERE id = ?", (topic_id,)
        ).fetchone()
        conn.close()
        return {"ok": True, "topic": dict(row)}
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e):
            return JSONResponse({"error": "主题名称已存在"}, status_code=409)
        return JSONResponse({"error": str(e)}, status_code=500)


@router.put("/api/research/topics/{topic_id}")
async def update_research_topic(topic_id: int, req: TopicUpdate):
    """修改研究主题。"""
    conn = get_connection()
    existing = conn.execute(
        "SELECT * FROM research_topics WHERE id = ?", (topic_id,)
    ).fetchone()
    if not existing:
        conn.close()
        return JSONResponse({"error": "主题不存在"}, status_code=404)

    fields = []
    values = []
    if req.name:
        fields.append("name = ?")
        values.append(req.name.strip())
    if req.description:
        fields.append("description = ?")
        values.append(req.description.strip())
    if req.depth:
        if req.depth not in ("quick", "standard", "deep"):
            conn.close()
            return JSONResponse({"error": "无效的深度模式"}, status_code=400)
        fields.append("depth = ?")
        values.append(req.depth)
    if req.status:
        if req.status not in ("active", "paused"):
            conn.close()
            return JSONResponse({"error": "无效的状态值"}, status_code=400)
        fields.append("status = ?")
        values.append(req.status)
    if not fields:
        conn.close()
        return JSONResponse({"error": "没有提供需要更新的字段"}, status_code=400)

    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(topic_id)
    conn.execute(
        f"UPDATE research_topics SET {', '.join(fields)} WHERE id = ?",
        values,
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM research_topics WHERE id = ?", (topic_id,)
    ).fetchone()
    conn.close()
    return {"ok": True, "topic": dict(row)}


@router.delete("/api/research/topics/{topic_id}")
async def delete_research_topic(topic_id: int):
    """删除研究主题。"""
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM research_topics WHERE id = ?", (topic_id,)
    ).fetchone()
    if not existing:
        conn.close()
        return JSONResponse({"error": "主题不存在"}, status_code=404)
    conn.execute("DELETE FROM research_topics WHERE id = ?", (topic_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ─── 研究触发 ────────────────────────────────────────────

@router.post("/api/research/stream")
async def research_stream(req: ResearchRequest):
    """流式触发研究 SSE 端点。"""
    from src.research.manager import ResearchManager

    manager = ResearchManager()
    topic_ids = req.topic_ids if req.topic_ids else None

    async def event_generator():
        async for event in manager.run_all_stream(
            topic_ids=topic_ids, model_id=req.model
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/research/reports")
async def list_research_reports(limit: int = 20, offset: int = 0):
    """获取研究报告列表（筛选 trigger 包含 research 的记录）。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, trigger, title, content, session_id, created_at "
        "FROM agent_reports "
        "WHERE trigger LIKE '%research%' "
        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    total_row = conn.execute(
        "SELECT COUNT(*) as cnt FROM agent_reports WHERE trigger LIKE '%research%'"
    ).fetchone()
    conn.close()
    items = [
        {
            "id": f"agent_report_{r['id']}",
            "type": "agent_report",
            "title": r["title"],
            "preview": (r["content"] or "")[:200],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    return {"items": items, "total": total_row["cnt"]}
```

- [ ] **Step 2: 将 research 操作加入 ACTIONS 列表**

在 `ACTIONS` 列表末尾（`send_email` 条目之后）添加：

```python
{
    "trigger": "scheduled_research",
    "name": "研究报告",
    "description": "为所有活跃研究主题生成深度研究报告，多源搜索并自动发送邮件",
    "icon": "🔬",
},
```

- [ ] **Step 3: 验证 API 路由可导入**

```bash
python -c "from src.web.routes import router; print(len(router.routes), 'routes'); print('OK')"
```

Expected: 输出路由数量后跟 `OK`

- [ ] **Step 4: Commit**

```bash
git add src/web/routes.py
git commit -m "feat: 添加研究主题 CRUD 和研究触发 API 端点"
```

---

### Task 7: 编写单元测试

**Files:**
- Create: `tests/test_research_manager.py`

- [ ] **Step 1: 编写 ResearchManager 测试**

```python
# tests/test_research_manager.py
"""ResearchManager 单元测试。"""
import pytest
from src.research.manager import ResearchManager, _slugify, DEPTH_ROUNDS


class TestSlugify:
    def test_slugify_chinese(self):
        assert _slugify("LLM Agent 最新进展") == "LLM_Agent_最新进展"

    def test_slugify_special_chars(self):
        result = _slugify("a/b:c?d*e")
        assert "/" not in result
        assert ":" not in result
        assert "?" not in result
        assert "*" not in result

    def test_slugify_long_name(self):
        long_name = "A" * 100
        result = _slugify(long_name)
        assert len(result) <= 60


class TestDepthRounds:
    def test_depth_config(self):
        assert DEPTH_ROUNDS["quick"] == 1
        assert DEPTH_ROUNDS["standard"] == 2
        assert DEPTH_ROUNDS["deep"] == 3


class TestResearchManagerInit:
    def test_init(self):
        manager = ResearchManager()
        assert manager.research_tool is not None
        assert manager.web_search_tool is not None

    def test_get_topics_empty(self):
        manager = ResearchManager()
        topics = manager._get_topics()
        assert isinstance(topics, list)

    def test_get_topic_not_found(self):
        manager = ResearchManager()
        result = manager._get_topic_by_id(99999)
        assert result is None
```

- [ ] **Step 2: 运行测试**

```bash
pytest tests/test_research_manager.py -v
```

Expected: 5 tests passed

- [ ] **Step 3: 编写 API 端点测试**

```python
# tests/test_research_api.py
"""研究 API 端点测试。"""
import pytest
from fastapi.testclient import TestClient
from src.web.routes import router
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
client = TestClient(app)


class TestResearchTopicsAPI:
    """主题 CRUD 接口测试（不依赖 Agent，只测端点逻辑）。"""

    def test_list_topics_empty(self):
        """获取主题列表 —— 无数据时返回空列表。"""
        response = client.get("/api/research/topics")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_create_topic(self):
        """创建主题。"""
        response = client.post(
            "/api/research/topics",
            json={"name": "测试主题", "description": "测试描述", "depth": "standard"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["topic"]["name"] == "测试主题"
        assert data["topic"]["depth"] == "standard"
        topic_id = data["topic"]["id"]

        # 清理
        client.delete(f"/api/research/topics/{topic_id}")

    def test_create_duplicate_topic(self):
        """创建重复主题应返回 409。"""
        # 先创建一个
        response = client.post(
            "/api/research/topics",
            json={"name": "重复测试主题", "depth": "standard"},
        )
        assert response.status_code == 200
        topic_id = response.json()["topic"]["id"]

        # 再创建同名的
        response = client.post(
            "/api/research/topics",
            json={"name": "重复测试主题", "depth": "standard"},
        )
        assert response.status_code == 409

        # 清理
        client.delete(f"/api/research/topics/{topic_id}")

    def test_update_topic(self):
        """修改主题。"""
        # 创建
        response = client.post(
            "/api/research/topics",
            json={"name": "更新测试主题", "depth": "quick"},
        )
        topic_id = response.json()["topic"]["id"]

        # 更新
        response = client.put(
            f"/api/research/topics/{topic_id}",
            json={"depth": "deep", "status": "paused"},
        )
        assert response.status_code == 200
        assert response.json()["topic"]["depth"] == "deep"
        assert response.json()["topic"]["status"] == "paused"

        # 清理
        client.delete(f"/api/research/topics/{topic_id}")

    def test_delete_topic(self):
        """删除主题。"""
        response = client.post(
            "/api/research/topics",
            json={"name": "删除测试主题", "depth": "quick"},
        )
        topic_id = response.json()["topic"]["id"]

        response = client.delete(f"/api/research/topics/{topic_id}")
        assert response.status_code == 200
        assert response.json()["ok"] is True

        # 再次删除应返回 404
        response = client.delete(f"/api/research/topics/{topic_id}")
        assert response.status_code == 404

    def test_list_research_reports(self):
        """研究报告列表端点。"""
        response = client.get("/api/research/reports")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
```

- [ ] **Step 4: 运行 API 测试**

```bash
pytest tests/test_research_api.py -v
```

Expected: 6 tests passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_research_manager.py tests/test_research_api.py
git commit -m "test: 添加 ResearchManager 和研究 API 单元测试"
```

---

### Task 8: 集成验证

- [ ] **Step 1: 运行全部测试确保无回归**

```bash
pytest tests/ -v
```

Expected: 所有测试通过，包括新增和已存在的测试。

- [ ] **Step 2: 验证完整的主题 CRUD 流程**

```bash
# 创建主题
curl -s -X POST http://localhost:8000/api/research/topics \
  -H "Content-Type: application/json" \
  -d '{"name":"集成测试主题","depth":"quick"}' | python -m json.tool

# 列出主题
curl -s http://localhost:8000/api/research/topics | python -m json.tool

# 删除主题（用实际 ID 替换）
curl -s -X DELETE http://localhost:8000/api/research/topics/1
```

Expected: 创建返回 ok:true，列表包含刚创建的主题，删除返回 ok:true

- [ ] **Step 3: 验证后端导入完整性**

```bash
python -c "
from src.research.manager import ResearchManager
from src.tools.deep_research import DeepResearchTool
from src.tools import ToolRegistry
from src.scheduler.jobs import scheduled_research
print('所有新模块导入成功')
"
```

Expected: `所有新模块导入成功`

- [ ] **Step 4: 最终 Commit（如有文档更新）**

```bash
git status
# 如有未提交的变更，提交之
```
