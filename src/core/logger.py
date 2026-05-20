"""Agent 日志系统 —— 控制台 + 文件双通道输出。

根 logger 在模块首次导入时自动初始化，
后续通过 get_logger(name) 获取子 logger 直接使用。
"""
import logging
import os
import sys
from datetime import datetime


def truncate(text: str, max_len: int = 500) -> str:
    """截断过长文本，尾部追加标记。"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "...[截断]"


def _init_root_logger() -> None:
    """初始化根 logger，配置控制台和文件双 Handler。

    模块加载时自动调用一次，重复调用不生效。
    """
    from src.core.config import config

    root = logging.getLogger("evomentor")
    if root.handlers:
        return  # 已初始化

    root.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台 Handler
    if config.LOG_TO_CONSOLE:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    # 文件 Handler
    if config.LOG_TO_FILE:
        try:
            log_dir = config.LOG_DIR
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            file_path = os.path.join(log_dir, f"{timestamp}.log")
            file_handler = logging.FileHandler(file_path, encoding="utf-8")
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError:
            # 目录创建失败时仅禁用文件日志，不抛出异常
            pass


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的子 logger。

    Usage:
        from src.core.logger import get_logger
        logger = get_logger("agent")
        logger.info("[USER] 消息内容")
    """
    _init_root_logger()
    return logging.getLogger(f"evomentor.{name}")
