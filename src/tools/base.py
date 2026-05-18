"""Tool 基类 —— 所有工具继承此基类，统一接口和元数据。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    content: str
    metadata: dict | None = None


class BaseTool(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...

    def to_llm_schema(self) -> dict:
        """生成 OpenAI 兼容的 Tool Definition。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.get_parameters_schema(),
            },
        }

    @abstractmethod
    def get_parameters_schema(self) -> dict:
        ...
