"""LLM 客户端抽象 —— 封装 DeepSeek API，预留切换接口。"""
import json
import time
from openai import OpenAI
from src.core.config import config


class LLMClient:
    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
        )
        self.model = config.DEEPSEEK_MODEL

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ) -> dict:
        """发送聊天请求，支持 Tool Calling。失败自动重试 3 次。"""
        last_error = None
        for attempt in range(config.LLM_MAX_RETRIES):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"
                response = self.client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                result = {
                    "content": choice.message.content or "",
                    "role": choice.message.role,
                }
                # DeepSeek thinking 模式要求将 reasoning_content 原样传回后续请求
                if hasattr(choice.message, "reasoning_content") and choice.message.reasoning_content:
                    result["reasoning_content"] = choice.message.reasoning_content
                if choice.message.tool_calls:
                    result["tool_calls"] = [
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments),
                        }
                        for tc in choice.message.tool_calls
                    ]
                return result
            except Exception as e:
                last_error = e
                if attempt < config.LLM_MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"LLM 调用失败（已重试 {config.LLM_MAX_RETRIES} 次）: {last_error}")

    def embed(self, text: str) -> list[float]:
        """生成文本的 embedding 向量。"""
        response = self.client.embeddings.create(
            model="deepseek-chat",
            input=text,
        )
        return response.data[0].embedding

    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
    ):
        """流式聊天，yield 每个 delta chunk。

        tool_calls 在流式模式下分片到达，调用方需自行累积拼接。
        重试仅覆盖初始 create() 调用；流开始后异常直接传播，避免已 yield 的数据块重复。
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        # 重试仅覆盖初始连接，流开始后不再重试
        last_error = None
        for attempt in range(config.LLM_MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(**kwargs)
                break  # 连接成功，退出重试循环
            except Exception as e:
                last_error = e
                if attempt < config.LLM_MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
        else:
            raise RuntimeError(
                f"LLM 流式调用失败（已重试 {config.LLM_MAX_RETRIES} 次）: {last_error}"
            )

        # 流开始后不重试，异常直接传播给调用方
        for chunk in response:
            delta = chunk.choices[0].delta
            yield_dict = {
                "content": delta.content or "",
                "role": delta.role or "",
                "tool_calls": delta.tool_calls or [],
                "finish_reason": chunk.choices[0].finish_reason or "",
            }
            # DeepSeek thinking 模式：delta 中可能包含 reasoning_content
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                yield_dict["reasoning_content"] = delta.reasoning_content
            yield yield_dict


llm = LLMClient()
