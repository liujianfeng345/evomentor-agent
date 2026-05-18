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
