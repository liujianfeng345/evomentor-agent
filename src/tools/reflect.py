"""反思工具 —— 自我进化的核心。审视短期记忆和决策日志，总结规律，更新知识图谱。"""
import json
from src.tools.base import BaseTool, ToolResult
from src.core.llm import llm
from src.memory.short_term import ShortTermMemory
from src.memory.long_term import lts
from src.db.vector_store import vector_store


class ReflectTool(BaseTool):
    name = "reflect"
    description = "审视近期的对话、GitHub 分析结果和决策日志，提炼经验教训，更新用户知识图谱。"

    def __init__(self, memory: ShortTermMemory) -> None:
        self.memory = memory

    async def execute(self) -> ToolResult:
        # 1. 收集反思素材
        conversations = self.memory.summarize_for_compression()
        decisions = lts.get_recent_decisions(limit=20)
        decisions_text = "\n".join(
            f"触发: {d['trigger']} | 结果: {d['outcome'][:200]}" for d in decisions
        )

        prompt = f"""你是 Evomentor 的反思模块，请审视以下信息，提炼经验教训：

## 近期对话
{conversations[:3000]}

## 近期决策
{decisions_text[:2000]}

请完成以下任务，输出 JSON 格式：

```json
{{
    "insights": [
        {{"category": "code_pattern|learning_tip|user_preference|research_insight",
          "title": "简短标题",
          "content": "详细内容"}}
    ],
    "knowledge_updates": [
        {{"topic": "知识领域", "proficiency": 1-5, "parent": "父领域"}}
    ],
    "summary": "一段话总结用户这段时间的学习状态"
}}
```

要求：
- 识别重复出现的问题模式（尤其是在代码中）
- 发现用户正在学习的方向
- 总结用户表现出的偏好
- 如果信息不足，对应字段填空数组即可"""

        response = llm.chat([{"role": "user", "content": prompt}])

        # 2. 解析结果
        try:
            data = self._parse_json(response["content"])
        except (json.JSONDecodeError, KeyError):
            return ToolResult(success=True, content="反思完成（无新发现）")

        # 3. 保存经验
        saved_count = 0
        for insight in data.get("insights", []):
            exp_id = lts.save_experience(
                category=insight.get("category", "learning_tip"),
                title=insight.get("title", "未命名"),
                content=insight.get("content", ""),
                source="reflection",
                confidence=0.5,
            )
            # 同时存入向量库
            text = f"{insight.get('title', '')}: {insight.get('content', '')}"
            vector_store.add("experience_embeddings", f"exp-{exp_id}", text)
            saved_count += 1

        # 4. 更新知识图谱
        for update in data.get("knowledge_updates", []):
            lts.update_knowledge(
                topic=update.get("topic", ""),
                proficiency=int(update.get("proficiency", 1)),
                parent=update.get("parent", ""),
            )

        # 5. 压缩短期记忆 —— 保留最近 10 条，其余清除
        recent = self.memory.get_all()[-10:]
        self.memory.clear()
        for m in recent:
            self.memory.add(m.role, m.content, m.tags, m.intent,
                           tool_calls=m.tool_calls, tool_call_id=m.tool_call_id)

        return ToolResult(
            success=True,
            content=f"反思完成。保存 {saved_count} 条经验，更新 {len(data.get('knowledge_updates', []))} 个知识点。\n摘要: {data.get('summary', '')}",
            metadata={"insights_count": saved_count, "summary": data.get("summary", "")},
        )

    def _parse_json(self, text: str) -> dict:
        """从 LLM 输出中提取 JSON 块。"""
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            return json.loads(text[start:end])
        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            return json.loads(text[start:end])
        return json.loads(text)

    def get_parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}
