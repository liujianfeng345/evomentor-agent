"""从环境变量加载配置。"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # DeepSeek
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    # GitHub
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_USERNAME: str = os.getenv("GITHUB_USERNAME", "")

    # SMTP
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # 数据库
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/evomentor.db")
    CHROMA_PATH: str = os.getenv("CHROMA_PATH", "data/chroma")

    # 调度
    IDLE_HOURS_BEFORE_TRIGGER: int = int(os.getenv("IDLE_HOURS_BEFORE_TRIGGER", "6"))

    # Agent
    SHORT_TERM_MAX_MESSAGES: int = 50
    LLM_MAX_RETRIES: int = 3

    # 模型注册表
    AVAILABLE_MODELS: list[dict] = [
        {
            "id": "deepseek-v4-flash",
            "name": "DeepSeek v4-flash",
            "provider": "deepseek",
            "model": os.getenv("DEEPSEEK_V4_FLASH_MODEL", "deepseek-chat"),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
            "icon": "⚡",
            "description": "快速响应，适合日常对话",
        },
        {
            "id": "deepseek-v4-pro",
            "name": "DeepSeek v4-pro",
            "provider": "deepseek",
            "model": os.getenv("DEEPSEEK_V4_PRO_MODEL", "deepseek-reasoner"),
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
            "icon": "🧠",
            "description": "深度推理，适合复杂问题",
        },
    ]

    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "deepseek-v4-flash")

    # Tavily
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

    SKILL_CONFIDENCE_THRESHOLD: float = 0.5


config = Config()
