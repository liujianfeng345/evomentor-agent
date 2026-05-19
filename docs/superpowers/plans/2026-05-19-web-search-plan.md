# Tavily 网络搜索工具 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `web_search` 工具，通过 Tavily API 提供互联网搜索能力

**Architecture:** 按现有 BaseTool 模式新增 WebSearchTool，注册到 ToolRegistry，更新 SYSTEM_PROMPT

**Tech Stack:** tavily-python SDK

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/core/config.py` | 修改 | 新增 TAVILY_API_KEY 配置 |
| `src/tools/web_search.py` | 新建 | WebSearchTool 实现 |
| `src/tools/__init__.py` | 修改 | 注册 web_search 到 ToolRegistry |
| `src/core/agent.py` | 修改 | SYSTEM_PROMPT 加入 web_search 描述 |

---

### Task 1: 配置 + 工具实现 + 注册 + 提示词

**Files:**
- Create: `src/tools/web_search.py`
- Modify: `src/core/config.py:33`、`src/tools/__init__.py:6,13`、`src/core/agent.py:15`

- [ ] **Step 1: 安装依赖**

```bash
pip install tavily-python
```

- [ ] **Step 2: 添加配置**

在 `src/core/config.py` 的 Config 类中，`DEFAULT_MODEL` 之后添加：

```python
    # Tavily
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
```

- [ ] **Step 3: 创建 WebSearchTool**

创建 `src/tools/web_search.py`：

```python
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
```

- [ ] **Step 4: 注册到 ToolRegistry**

在 `src/tools/__init__.py` 中：

第 6 行之后添加 import：
```python
from src.tools.web_search import WebSearchTool
```

在 `self.tools` 字典中（约第 13-19 行）添加：
```python
            "web_search": WebSearchTool(),
```

- [ ] **Step 5: 更新 SYSTEM_PROMPT**

在 `src/core/agent.py` 的 SYSTEM_PROMPT 中，工具列表末尾（`- **send_email**` 行之后）添加：

```
- **web_search**: 搜索互联网获取最新网页信息，适合查询新闻、实时数据、技术资料等通用内容。
```

- [ ] **Step 6: 验证**

```bash
pip install tavily-python && python -c "from src.tools import ToolRegistry; from src.memory.short_term import ShortTermMemory; r = ToolRegistry(ShortTermMemory()); print('web_search' in r.list_names())"
```
Expected: `True`

- [ ] **Step 7: Commit**

```bash
git add src/core/config.py src/tools/web_search.py src/tools/__init__.py src/core/agent.py
git commit -m "feat: 新增 Tavily 网络搜索工具 web_search"
```

---

### Task 2: 集成测试

**Files:**
- Modify: `tests/test_streaming.py`

- [ ] **Step 1: 添加测试**

在 `tests/test_streaming.py` 末尾追加：

```python
def test_web_search_tool_schema():
    """验证 web_search 工具的 LLM Schema 正确。"""
    from src.tools.web_search import WebSearchTool
    tool = WebSearchTool()
    schema = tool.to_llm_schema()
    assert schema["function"]["name"] == "web_search"
    params = schema["function"]["parameters"]
    assert "query" in params["properties"]
    assert params["required"] == ["query"]
    assert "search_depth" in params["properties"]
    assert set(params["properties"]["search_depth"]["enum"]) == {"basic", "advanced"}


@pytest.mark.asyncio
async def test_web_search_execute_requires_api_key():
    """验证 web_search 工具在无 API key 时可正常执行（返回错误而非崩溃）。"""
    from src.tools.web_search import WebSearchTool
    tool = WebSearchTool()
    result = await tool.execute(query="test", search_depth="basic")
    # 无论是否有 API key，都不应该抛出异常
    assert result is not None
    assert hasattr(result, "content")
```

- [ ] **Step 2: 运行测试**

```bash
pytest tests/test_streaming.py::test_web_search_tool_schema tests/test_streaming.py::test_web_search_execute_requires_api_key -v
```
Expected: 2 PASSED

- [ ] **Step 3: 运行全部测试无回归**

```bash
pytest tests/test_streaming.py -v
```
Expected: 10 PASSED

- [ ] **Step 4: Commit**

```bash
git add tests/test_streaming.py
git commit -m "test: 添加 web_search 工具 schema 和执行测试"
```

---

## 变更文件汇总

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/core/config.py` | 修改 | +1 行：TAVILY_API_KEY |
| `src/tools/web_search.py` | 新建 | ~50 行：WebSearchTool 实现 |
| `src/tools/__init__.py` | 修改 | +2 行：import + 注册 |
| `src/core/agent.py` | 修改 | +1 行：SYSTEM_PROMPT |
| `tests/test_streaming.py` | 修改 | +2 测试 |
