"""Tool 基类单元测试。"""
import pytest
from src.tools.base import ToolResult, BaseTool


class TestToolResult:
    def test_success_result(self):
        r = ToolResult(success=True, content="ok")
        assert r.success is True
        assert r.content == "ok"
        assert r.metadata is None

    def test_failure_result_with_metadata(self):
        r = ToolResult(success=False, content="error", metadata={"code": 500})
        assert r.success is False
        assert r.metadata["code"] == 500


class TestBaseTool:
    def test_to_llm_schema(self):
        class DummyTool(BaseTool):
            name = "dummy"
            description = "A dummy tool for testing"

            async def execute(self, **kwargs):
                return ToolResult(success=True, content="done")

            def get_parameters_schema(self):
                return {
                    "type": "object",
                    "properties": {
                        "arg1": {"type": "string", "description": "参数1"},
                    },
                    "required": ["arg1"],
                }

        tool = DummyTool()
        schema = tool.to_llm_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "dummy"
        assert schema["function"]["description"] == "A dummy tool for testing"
        assert "arg1" in schema["function"]["parameters"]["properties"]
