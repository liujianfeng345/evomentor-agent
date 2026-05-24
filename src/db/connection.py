"""数据库连接 —— 提供统一的 SQLite 连接获取接口。"""
import sqlite3
import os
from src.core.config import config


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
