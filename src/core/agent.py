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

    async def handle_message_stream(self, user_message: str):
        """流式版 handle_message，返回 async generator，yield SSE 事件 dict。"""
        try:
            context = retrieve_relevant_context(user_message)
            self.short_term.add("user", user_message)

            async for event in self._agent_loop_stream(
                trigger="user_message",
                initial_context=context,
                max_rounds=5,
            ):
                yield event
        except Exception as e:
            yield {"type": "error", "message": f"处理失败: {str(e)}"}
        finally:
            self._persist_and_clear()

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

        self._persist_and_clear()
        return final_response

    def _persist_and_clear(self):
        """持久化对话到长期存储，清除短期记忆。"""
        for msg in self.short_term.get_all():
            lts.save_conversation(
                role=msg.role, content=msg.content,
                tags=msg.tags, intent=msg.intent,
                session_id=self.session_id,
            )
        self.short_term.clear()

    async def _agent_loop_stream(self, trigger: str, initial_context: str, max_rounds: int):
        """流式版 Agent 循环，yield SSE 事件 dict。"""
        context = initial_context

        for _ in range(max_rounds):
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": f"## 相关记忆\n{context}"},
            ]
            messages.extend(self.short_term.get_for_llm())

            tool_calls_buffer: dict[int, dict] = {}
            content_buffer = ""
            reasoning_buffer = ""

            for chunk in llm.chat_stream(messages, tools=self.tools.get_schemas()):
                if chunk["tool_calls"]:
                    for tc in chunk["tool_calls"]:
                        idx = tc.index
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name or "",
                                "arguments": "",
                            }
                        if tc.function.arguments:
                            tool_calls_buffer[idx]["arguments"] += tc.function.arguments

                elif chunk["content"]:
                    content_buffer += chunk["content"]
                    yield {"type": "text", "content": chunk["content"]}

                if chunk.get("reasoning_content"):
                    reasoning_buffer += chunk["reasoning_content"]

            # 如果没有 tool_calls，直接结束
            if not tool_calls_buffer:
                if content_buffer:
                    self.short_term.add("assistant", content_buffer)
                yield {"type": "done"}
                return

            # 有 tool_calls：通知前端、执行工具、继续循环
            tools_list = [{"name": v["name"]} for v in tool_calls_buffer.values()]
            yield {"type": "tool_start", "tools": tools_list}

            # 记录决策
            decision_tool_names = [v["name"] for v in tool_calls_buffer.values()]
            lts.log_decision(
                trigger=trigger,
                tool_calls=decision_tool_names,
                reasoning=content_buffer,
                outcome="",
            )

            # 构建 assistant tool_calls 消息
            tool_calls_schema = [
                {
                    "id": v["id"],
                    "type": "function",
                    "function": {"name": v["name"], "arguments": v["arguments"]},
                }
                for v in tool_calls_buffer.values()
            ]
            self.short_term.add_assistant_tool_calls(
                content_buffer, tool_calls_schema,
                reasoning_content=reasoning_buffer or None,
            )

            for tc_data in tool_calls_buffer.values():
                name = tc_data["name"]
                yield {"type": "tool_step", "name": name, "status": "running"}

                tool = self.tools.get(name)
                if tool:
                    try:
                        args = json.loads(tc_data["arguments"])
                        result = await tool.execute(**args)
                        self.short_term.add_tool_result(
                            name, result.content,
                            tool_call_id=tc_data["id"],
                        )
                        if result.metadata:
                            context += f"\n{name} 元数据: {result.metadata}"
                        yield {"type": "tool_step", "name": name, "status": "done"}
                    except (json.JSONDecodeError, Exception) as e:
                        self.short_term.add_tool_result(
                            name, f"执行失败: {e}",
                            tool_call_id=tc_data["id"],
                        )
                        yield {"type": "tool_step", "name": name, "status": "error"}
                else:
                    yield {"type": "tool_step", "name": name, "status": "error"}

            self.short_term.add("system", "工具执行完毕，请根据结果决定下一步。")
            yield {"type": "tool_end"}

        # max_rounds 用尽
        yield {"type": "done"}
