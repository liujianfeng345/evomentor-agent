"""短期记忆 —— 基于内存的消息列表，有容量上限。"""
from dataclasses import dataclass, field
from datetime import datetime
from src.core.config import config


@dataclass
class Message:
    role: str
    content: str
    tags: list[str] = field(default_factory=list)
    intent: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None

    def to_dict(self) -> dict:
        result = {
            "role": self.role,
            "content": self.content,
            "tags": self.tags,
            "intent": self.intent,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        return result


class ShortTermMemory:
    def __init__(self) -> None:
        self.messages: list[Message] = []

    def add(self, role: str, content: str, tags: list[str] | None = None,
            intent: str = "", tool_calls: list[dict] | None = None,
            tool_call_id: str | None = None) -> None:
        self.messages.append(Message(
            role=role, content=content,
            tags=tags or [], intent=intent,
            tool_calls=tool_calls, tool_call_id=tool_call_id,
        ))
        self._trim()

    def add_assistant_tool_calls(self, content: str, tool_calls_schema: list[dict]) -> None:
        """添加包含 tool_calls 的 assistant 消息（符合 OpenAI API 格式）。"""
        self.messages.append(Message(
            role="assistant",
            content=content or None,
            tool_calls=tool_calls_schema if tool_calls_schema else None,
        ))

    def add_tool_result(self, tool_name: str, result: str, tool_call_id: str = "") -> None:
        self.messages.append(Message(
            role="tool",
            content=f"[{tool_name}] {result}",
            tool_call_id=tool_call_id or None,
        ))

    def get_all(self) -> list[Message]:
        return list(self.messages)

    def get_for_llm(self) -> list[dict]:
        result = []
        for m in self.messages:
            msg = {"role": m.role, "content": m.content}
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            result.append(msg)
        return result

    def is_full(self) -> bool:
        return len(self.messages) >= config.SHORT_TERM_MAX_MESSAGES

    def clear(self) -> None:
        self.messages.clear()

    def _trim(self) -> None:
        while len(self.messages) > config.SHORT_TERM_MAX_MESSAGES:
            self.messages.pop(0)

    def summarize_for_compression(self) -> str:
        """将当前对话内容压缩为一段摘要文本，供反思 Tool 使用。"""
        lines = []
        for m in self.messages:
            lines.append(f"[{m.role}] {(m.content or '')[:200]}")
        return "\n".join(lines)
