"""Agent 核心循环 —— 感知→思考→行动→观察。"""
import json
import uuid
from src.core.llm import llm
from src.memory.short_term import ShortTermMemory
from src.memory.long_term import lts
from src.memory.retrieval import retrieve_relevant_context
from src.tools import ToolRegistry

SYSTEM_PROMPT = """你是 Evomentor，一个能自我进化的个人学习助手。

## 核心使命
帮助用户高效学习成长。你通过以下工具实现这一目标：
- **chat**: 与用户交流，解答问题
- **github_analyze**: 分析用户的 GitHub 提交和 Star 仓库
- **research**: 搜索最新的论文、论坛和 GitHub 仓库
- **reflect**: 审视近期对话，提炼经验，自我进化
- **skill_manager**: 将稳定经验转化为可复用的 Skill
- **send_email**: 发送学习周报邮件给用户

## 行为准则
- 主动感知用户的学习状态和需求
- 准确判断何时该聊天、分析、研究或反思
- 对话自然、有帮助、有深度
- 当用户消息是简单问候时，只用 chat 回复，不要调用其他工具
- 当用户问及具体技术问题时，先用 chat 回复，视情况补充 research"""


class Agent:
    def __init__(self) -> None:
        self.short_term = ShortTermMemory()
        self.tools = ToolRegistry(self.short_term)
        self.session_id = str(uuid.uuid4())[:8]

    async def handle_message(self, user_message: str) -> str:
        """被动触发：处理用户消息。"""
        # 感知
        context = retrieve_relevant_context(user_message)
        self.short_term.add("user", user_message)

        # 思考 + 行动 + 观察 循环（最多 5 轮）
        return await self._agent_loop(
            trigger="user_message",
            initial_context=context,
            max_rounds=5,
        )

    async def handle_scheduled(self, trigger: str) -> str:
        """主动触发：处理定时任务。"""
        context = retrieve_relevant_context(trigger)

        prompt_map = {
            "periodic_check": "现在是定时检查。请分析用户的 GitHub 最近提交，搜索前沿方向，反思近期对话并准备学习周报。如果一切正常，最后发送邮件。",
            "reflect": "现在是自我反思时间。请审视近期的所有对话和分析结果，提炼经验，更新知识图谱，必要时创建 Skill。",
        }

        initial = prompt_map.get(trigger, f"执行任务：{trigger}")
        self.short_term.add("system", initial)

        return await self._agent_loop(
            trigger=trigger,
            initial_context=context,
            max_rounds=8,
        )

    async def _agent_loop(self, trigger: str, initial_context: str, max_rounds: int) -> str:
        """核心循环：思考 → 行动 → 观察，最多 max_rounds 轮。"""
        context = initial_context
        final_response = ""

        for _ in range(max_rounds):
            # 思考：让 LLM 决定调用哪个 Tool
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": f"## 相关记忆\n{context}"},
            ]
            messages.extend(self.short_term.get_for_llm())

            response = llm.chat(messages, tools=self.tools.get_schemas())

            # 记录决策
            tool_calls = response.get("tool_calls", [])
            lts.log_decision(
                trigger=trigger,
                tool_calls=[tc["name"] for tc in tool_calls],
                reasoning=response.get("content", ""),
                outcome="",
            )

            # 如果没有 tool_calls，说明 LLM 认为该直接回复
            if not tool_calls:
                final_response = response["content"]
                self.short_term.add("assistant", final_response)
                break

            # 将 LLM 的 tool_calls 构建为 OpenAI 格式
            tool_calls_schema = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                    },
                }
                for tc in tool_calls
            ]

            # 先行执行 Tool（此时 short_term 中尚无 tool_calls，工具不会看到它们）
            outcomes = []
            tool_results: list[dict] = []
            for tc in tool_calls:
                tool = self.tools.get(tc["name"])
                if tool:
                    result = await tool.execute(**tc["arguments"])
                    outcomes.append(f"[{tc['name']}] {result.content}")
                    tool_results.append({
                        "tool_name": tc["name"],
                        "content": result.content,
                        "tool_call_id": tc["id"],
                    })
                    if result.metadata:
                        context += f"\n{tc['name']} 元数据: {result.metadata}"

            # 工具执行完毕后再写入 short_term，保证 tool_calls 紧跟 tool 结果（满足 OpenAI API 顺序）
            self.short_term.add_assistant_tool_calls(
                response.get("content", ""), tool_calls_schema,
                reasoning_content=response.get("reasoning_content", ""),
            )
            for tr in tool_results:
                self.short_term.add_tool_result(tr["tool_name"], tr["content"], tool_call_id=tr["tool_call_id"])

            # 观察：汇总结果，继续循环
            self.short_term.add("system", "工具执行完毕，请根据结果决定下一步。")
            if outcomes:
                final_response = "\n".join(outcomes)

        # 保存对话到长期存储
        for msg in self.short_term.get_all():
            lts.save_conversation(
                role=msg.role, content=msg.content,
                tags=msg.tags, intent=msg.intent,
                session_id=self.session_id,
            )

        # 清除短期记忆，避免下次调用时残留历史 tool_calls 导致 API 错误
        self.short_term.clear()

        return final_response
