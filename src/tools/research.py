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
                # 同时写入 research_findings 表，使 API 可查询
                lts.save_research_finding(
                    topic=topic,
                    source_type="multi",
                    url="",
                    summary=full[:500],
                    relevance_score=0.6,
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
