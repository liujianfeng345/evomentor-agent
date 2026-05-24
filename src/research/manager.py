# src/research/manager.py
"""ResearchManager —— 多轮深度研究管道，独立于 Agent 循环运行。"""
import asyncio
import json
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
                    topic_name, findings, round_num, depth, model_id=model_id
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
        return await self._generate_report(topic_name, "\n\n".join(all_findings), model_id=model_id)

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
                    topic_name, findings, round_num, depth, model_id=model_id
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
        report = await self._generate_report(topic_name, "\n\n".join(all_findings), model_id=model_id)
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
        self, topic: str, findings: str, round_num: int, depth: str,
        model_id: str = "",
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
                model_id=model_id,
            )
            content = response.get("content", "{}")
            # 提取 JSON（LLM 可能在前后加了说明文字）
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                return json.loads(json_match.group())
            return {"continue": False, "gaps": "", "summary": content[:200]}
        except Exception as e:
            research_logger.warning("[RESEARCH] 分析失败: %s", str(e))
            return {"continue": False, "gaps": "", "summary": findings[:200]}

    # ── 报告生成 ────────────────────────────────────────

    async def _generate_report(self, topic: str, all_findings: str, model_id: str = "") -> str:
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
                model_id=model_id,
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
