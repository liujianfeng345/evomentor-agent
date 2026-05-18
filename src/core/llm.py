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


llm = LLMClient()
