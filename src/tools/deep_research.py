# src/tools/deep_research.py
"""深度研究工具 —— Agent 可调用此工具对指定主题进行深度研究。"""
from src.tools.base import BaseTool, ToolResult
from src.research.manager import ResearchManager


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
