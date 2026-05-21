"""对话工具 —— 接收用户消息，生成回复并标注意图和标签。"""
import json
from src.tools.base import BaseTool, ToolResult
from src.core.llm import llm
from src.memory.short_term import ShortTermMemory
from src.memory.retrieval import retrieve_relevant_context


class ChatTool(BaseTool):
    name = "chat"
    description = "与用户对话。接收用户消息，结合记忆上下文生成回复，自动标注话题标签和用户意图。"

    def __init__(self, memory: ShortTermMemory) -> None:
        self.memory = memory

    async def execute(self, message: str, session_id: str = "default") -> ToolResult:
        # 检索相关记忆
        context = retrieve_relevant_context(message)

        # 构建 System Prompt
        system_prompt = f"""你是 Evomentor，一个能自我进化的个人学习助手。
你的目标是帮助用户高效学习，持续跟踪他们的成长。

## 用户知识背景
{context}

## 行为指南
- 回答要精准、有深度，避免泛泛而谈
- 发现用户的薄弱点时，温和指出并给出学习建议
- 记住用户的偏好和技术栈
- 回复末尾标注：##标签: <逗号分隔的话题标签>
"""
        messages = [{"role": "system", "content": system_prompt}]
        # 只取用户和助手消息，过滤掉 agent 循环内部的 tool_calls/tool 消息
        for m in self.memory.get_for_llm():
            if m["role"] in ("user", "assistant") and not m.get("tool_calls"):
                messages.append(m)
        messages.append({"role": "user", "content": message})

        response = llm.chat(messages)

        content = response["content"]
        # 解析标签
        tags, intent = self._parse_meta(content)

        return ToolResult(success=True, content=content, metadata={"tags": tags, "intent": intent})

    def _parse_meta(self, content: str) -> tuple[list[str], str]:
        tags = []
        intent = ""
        if "##标签:" in content:
            tag_part = content.split("##标签:")[-1].strip()
            tags = [t.strip() for t in tag_part.split(",") if t.strip()]
        return tags, intent

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "用户消息内容"},
                "session_id": {"type": "string", "description": "会话ID，默认 default"},
            },
            "required": ["message"],
        }
