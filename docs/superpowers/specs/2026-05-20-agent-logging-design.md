# Agent 日志系统设计

## 概述

为 Evomentor 项目添加结构化日志系统，记录 Agent 循环、工具调用、LLM 交互等关键事件，支持控制台和文件双通道输出。

## 模块结构

```
src/core/logger.py   ← 新增：封装 logging 配置 + 截断工具函数
src/core/config.py   ← 修改：添加 4 个日志相关配置项
src/core/agent.py    ← 修改：在关键节点插入日志调用
src/core/llm.py      ← 修改：LLM 调用处插入日志
.env.example         ← 修改：添加日志配置示例
.gitignore           ← 修改：忽略 logs/ 目录
```

## 配置项

在 `Config` 类中新增 4 个环境变量配置：

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| `LOG_TO_CONSOLE` | `LOG_TO_CONSOLE` | `true` | 是否输出到控制台 |
| `LOG_TO_FILE` | `LOG_TO_FILE` | `true` | 是否输出到文件 |
| `LOG_DIR` | `LOG_DIR` | `logs` | 日志目录（相对于项目根目录） |
| `LOG_TRUNCATE_LENGTH` | `LOG_TRUNCATE_LENGTH` | `500` | 工具输出/LLM 回复截断长度 |

布尔值解析：`"1"`, `"true"`, `"yes"` 视为 True（不区分大小写），其余视为 False。

## 日志文件

- 目录：项目根目录下的 `logs/`，不存在时自动创建
- 文件名：`YYYY-MM-DD_HH-MM-SS.log`（启动时间戳）
- 编码：UTF-8
- 每次启动创建一个新文件

## 日志格式

统一格式（控制台和文件相同）：
```
[2026-05-20 14:30:01] [USER] 帮我分析最近的 GitHub 提交
[2026-05-20 14:30:02] [LLM] 决定调用: github_analyze
[2026-05-20 14:30:02] [TOOL] github_analyze 开始执行
[2026-05-20 14:30:05] [TOOL] github_analyze 完成 (3.2s): 最近 5 次提交分析如下：...
[2026-05-20 14:30:06] [LLM] 根据分析结果，你最近的提交主要集中在...
```

截断规则：内容超过配置长度时，截取前 N 字符，尾部追加 `...[截断]`。

## 日志记录点

### Agent 层（`agent.py`）

| 分类标签 | 触发时机 | 记录内容 |
|----------|----------|----------|
| `[USER]` | 收到用户消息 | 消息内容 |
| `[LLM]` | LLM 决定调用工具 | 工具名称列表 |
| `[LLM]` | LLM 给出纯文本回复 | 回复内容（可能截断） |
| `[SYSTEM]` | 定时任务触发 | trigger 类型 |
| `[SYSTEM]` | 循环结束/持久化 | session_id, round 数 |

### 工具执行（`agent.py`）

| 分类标签 | 触发时机 | 记录内容 |
|----------|----------|----------|
| `[TOOL]` | 工具开始执行 | 工具名称 |
| `[TOOL]` | 工具执行完成 | 工具名称 + 耗时 + 返回内容（可能截断） |
| `[TOOL]` | 工具执行失败 | 工具名称 + 耗时 + 错误信息 |

### LLM 层（`llm.py`）

| 分类标签 | 触发时机 | 记录内容 |
|----------|----------|----------|
| `[LLM]` | API 调用 | 模型名称 |
| `[LLM]` | API 调用完成 | 耗时 |
| `[LLM]` | API 调用失败 | 重试次数 + 错误信息 |

## `src/core/logger.py` 接口

```python
# 获取 logger（模块级单例，根 logger 在首次 import 时自动初始化）
from src.core.logger import get_logger

logger = get_logger("agent")  # 或 "llm", "tool" 等

# 使用
logger.info("[USER] 帮我分析 GitHub")
logger.info("[TOOL] github_analyze 完成 (3.2s): ...")

# 截断工具函数
from src.core.logger import truncate
truncate("很长的文本...", max_len=500)  # → "很长的文本..." 或 "很长...[截断]"
```

内部实现：
- `_init_root_logger()` 在模块加载时自动执行，配置 StreamHandler（控制台）+ FileHandler（文件）
- 控制台和文件各自独立的 Handler，可单独开关
- Formatter：`[%(asctime)s] %(message)s`，日期格式 `%Y-%m-%d %H:%M:%S`
- 日志级别统一为 `INFO`

## 错误处理

- 日志写入静默失败：日志模块本身不抛异常，不影响 Agent 正常运行
- 日志目录创建失败时，仅禁用文件 Handler，控制台 Handler 仍正常工作
- 文件写入异常由 logging 模块内置的 `handleError` 处理（默认输出到 stderr）

## 后续不做的

- 不做日志轮转（每次启动新文件已避免单文件膨胀）
- 不做 DEBUG 级别（当前需求不需要）
- 不做 JSON 格式输出
- 不做日志检索/分析功能
