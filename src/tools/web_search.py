"""网络搜索工具 —— 通过 Tavily API 搜索互联网获取最新信息。"""
from tavily import TavilyClient
from src.tools.base import BaseTool, ToolResult
from src.core.config import config


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "搜索互联网获取最新信息、事实和实时数据。适合查询新闻、技术资料、产品信息等通用网页内容。"

    async def execute(self, query: str, search_depth: str = "basic") -> ToolResult:
        client = TavilyClient(api_key=config.TAVILY_API_KEY)
        depth = search_depth if search_depth in ("basic", "advanced") else "basic"
        try:
            response = client.search(query=query, search_depth=depth, max_results=5)
            results = response.get("results", [])
            if not results:
                return ToolResult(success=True, content=f"未找到与「{query}」相关的网页。")

            lines = [f"## 网络搜索: {query}\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. **[{r.get('title', '')}]({r.get('url', '')})**")
                lines.append(f"   {r.get('content', '')[:300]}")
            return ToolResult(success=True, content="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, content=f"搜索失败: {str(e)}")

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或问题",
                },
                "search_depth": {
                    "type": "string",
                    "enum": ["basic", "advanced"],
                    "description": "basic=快速搜索(默认)，advanced=深度搜索(递归跟踪链接)",
                },
            },
            "required": ["query"],
        }
