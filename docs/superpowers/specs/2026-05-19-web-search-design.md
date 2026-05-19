# Tavily 网络搜索工具 — 设计文档

日期：2026-05-19

## 需求概述

新增 `web_search` 工具，通过 Tavily API 提供互联网搜索能力。与现有 `research` 工具互补（research=学术/代码，web_search=通用网页）。

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 工具定位 | 独立 `web_search` Tool | 与 research 语义清晰区分 |
| 搜索深度 | LLM 可选择 basic/advanced | 灵活平衡速度与深度 |
| 结果数量 | 固定 5 条 | 足够 LLM 综合回答，不过度消耗 token |
| SDK | tavily-python 官方库 | 维护成本低 |

## 架构

```
LLM 决定调用 web_search → WebSearchTool.execute(query, search_depth)
    → TavilyClient.search() → structured results
    → 格式化为 Markdown → ToolResult → 反馈给 LLM → LLM 综合回答
```

## 变更文件

### 1. `src/core/config.py` — 新增 API key 配置

```python
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
```

### 2. `src/tools/web_search.py` — 新建工具文件

```python
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
```

### 3. `src/tools/__init__.py` — 注册新工具

```python
from src.tools.web_search import WebSearchTool

# 在 ToolRegistry.__init__ 的 self.tools 中新增：
"web_search": WebSearchTool(),
```

### 4. `src/core/agent.py` — 更新 SYSTEM_PROMPT

在工具列表区追加一行：
```
- **web_search**: 搜索互联网获取最新网页信息，适合查询新闻、实时数据、技术资料等通用内容
```

### 5. 依赖安装

```bash
pip install tavily-python
```

`requirements.txt` 中追加一行：
```
tavily-python
```

## 与现有 research 工具的分工

| 工具 | 搜索源 | 典型场景 |
|------|--------|----------|
| `web_search` | Tavily（通用网页） | "React 19 新特性"、"今天天气"、技术文档 |
| `research` | arXiv / HN / GitHub | "最新机器学习论文"、热门开源项目、技术讨论 |

## 数据流

```
用户: "Python 3.14 有什么新特性？"
    → Agent 判断: 需要 web_search
    → WebSearchTool.execute(query="Python 3.14 new features", search_depth="basic")
    → Tavily API 返回 5 条网页结果
    → ToolResult: Markdown 格式列表
    → LLM 结合搜索结果生成回答
```

## 错误处理

- Tavily API key 未配置 → `TavilyClient` 初始化失败，返回 `success=False`
- API 调用超时 → `try/except` 捕获，返回错误信息给 LLM
- 搜索结果为空 → 返回"未找到"提示，LLM 可以换关键词重试

## 测试要点

1. WebSearchTool 正确注册到 ToolRegistry
2. LLM Schema 包含 query（必填）和 search_depth（可选）
3. basic 搜索返回 5 条结果
4. advanced 搜索正常调用
5. 无效 API key 时工具返回错误而非崩溃
6. 搜索结果为空时返回友好提示
