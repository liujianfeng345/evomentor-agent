# Agent 日志系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Evomentor 添加双通道（控制台+文件）日志系统，记录工具调用、耗时、LLM 交互和用户消息。

**Architecture:** 基于 Python 内置 `logging` 模块，在 `src/core/logger.py` 中封装根 logger 初始化（StreamHandler + FileHandler）。Agent 和 LLM 模块通过 `get_logger()` 获取子 logger 记录结构化日志。

**Tech Stack:** Python `logging`（标准库），无额外依赖

---



### 文件变更总览

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/core/config.py` | 修改 | 新增 4 个日志配置项 |
| `src/core/logger.py` | 创建 | 根 logger 初始化、`get_logger()`、`truncate()` |
| `.env.example` | 修改 | 添加日志配置示例 |
| `.gitignore` | 修改 | 忽略 `logs/` 目录 |
| `src/core/agent.py` | 修改 | Agent 循环中插入日志 |
| `src/core/llm.py` | 修改 | LLM 调用处插入日志 |
| `tests/test_logger.py` | 创建 | `truncate()` 和 `get_logger()` 单元测试 |

---

### Task 1: 添加日志配置项到 Config

**Files:**
- Modify: `src/core/config.py:65`

在 `Config` 类末尾（`SKILL_CONFIDENCE_THRESHOLD` 之后）添加 4 个日志配置项。

- [ ] **Step 1: 添加日志配置项**

```python
# 日志
LOG_TO_CONSOLE: bool = os.getenv("LOG_TO_CONSOLE", "true").lower() in ("1", "true", "yes")
LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "true").lower() in ("1", "true", "yes")
LOG_DIR: str = os.getenv("LOG_DIR", "logs")
LOG_TRUNCATE_LENGTH: int = int(os.getenv("LOG_TRUNCATE_LENGTH", "500"))
```

- [ ] **Step 2: 提交**

```bash
git add src/core/config.py
git commit -m "feat: 添加日志配置项到 Config

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 编写 truncate() 和 get_logger() 测试

**Files:**
- Create: `tests/test_logger.py`

- [ ] **Step 1: 编写测试文件**

```python
"""日志模块单元测试。"""
import os
import sys
import pytest


class TestTruncate:
    """测试截断工具函数。"""

    def test_short_text_unchanged(self):
        """短文本不截断。"""
        from src.core.logger import truncate
        assert truncate("hello", max_len=10) == "hello"

    def test_exact_length_unchanged(self):
        """恰好等于长度限制不截断。"""
        from src.core.logger import truncate
        assert truncate("1234567890", max_len=10) == "1234567890"

    def test_long_text_truncated(self):
        """超长文本截断并加标记。"""
        from src.core.logger import truncate
        result = truncate("123456789012345", max_len=10)
        assert result == "1234567890...[截断]"
        assert len(result) <= 10 + len("...[截断]")

    def test_custom_max_len(self):
        """自定义截断长度。"""
        from src.core.logger import truncate
        result = truncate("abcdefghijklmnop", max_len=5)
        assert result == "abcde...[截断]"

    def test_empty_string(self):
        """空字符串不报错。"""
        from src.core.logger import truncate
        assert truncate("", max_len=10) == ""

    def test_chinese_text(self):
        """中文文本也可正确截断。"""
        from src.core.logger import truncate
        result = truncate("你好世界这是一个很长的文本用来测试截断功能", max_len=10)
        assert result.endswith("...[截断]")


class TestGetLogger:
    """测试日志获取函数。"""

    def test_returns_logger(self):
        """get_logger 返回 Logger 实例。"""
        from src.core.logger import get_logger
        import logging
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_same_name_same_logger(self):
        """同一名称返回同一 logger 实例。"""
        from src.core.logger import get_logger
        logger1 = get_logger("test_same")
        logger2 = get_logger("test_same")
        assert logger1 is logger2
```

- [ ] **Step 2: 运行测试验证失败（logger.py 尚不存在）**

```bash
pytest tests/test_logger.py::TestTruncate::test_short_text_unchanged -v
```
期望: FAIL — `ModuleNotFoundError: No module named 'src.core.logger'`

- [ ] **Step 3: 提交**

```bash
git add tests/test_logger.py
git commit -m "test: 添加 logger 模块单元测试

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 创建日志模块

**Files:**
- Create: `src/core/logger.py`

- [ ] **Step 1: 创建 logger.py**

```python
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
```

- [ ] **Step 2: 运行 truncate 测试验证**

```bash
pytest tests/test_logger.py::TestTruncate -v
```
期望: 6 tests PASS

- [ ] **Step 3: 运行 get_logger 测试验证**

注意：get_logger 测试依赖项目根目录结构，需从项目根运行：
```bash
pytest tests/test_logger.py::TestGetLogger -v
```

- [ ] **Step 4: 提交**

```bash
git add src/core/logger.py
git commit -m "feat: 创建日志模块 logger.py

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 更新 .env.example 和 .gitignore

**Files:**
- Modify: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: 在 .env.example 末尾添加日志配置**

在 `.env.example` 的 `IDLE_HOURS_BEFORE_TRIGGER=6` 后追加：

```ini
# 日志配置
LOG_TO_CONSOLE=true
LOG_TO_FILE=true
LOG_DIR=logs
LOG_TRUNCATE_LENGTH=500
```

- [ ] **Step 2: 在 .gitignore 添加 logs/ 目录**

在 `data/` 之后添加：

```
# 日志
logs/
```

- [ ] **Step 3: 提交**

```bash
git add .env.example .gitignore
git commit -m "chore: 添加日志相关环境变量示例和 gitignore

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: Agent 循环（非流式）添加日志

**Files:**
- Modify: `src/core/agent.py`

在 `_agent_loop` 方法和 `handle_message`/`handle_scheduled` 方法中插入日志调用。

- [ ] **Step 1: 添加 import**

在 `src/core/agent.py` 顶部 import 区域添加：

```python
import time
from src.core.logger import get_logger, truncate
```

位置：在现有 `import uuid` 之后。

- [ ] **Step 2: 模块级 logger 实例**

在 `import` 区域之后、`SYSTEM_PROMPT` 之前添加：

```python
agent_logger = get_logger("agent")
```

- [ ] **Step 3: handle_message 添加用户消息日志**

在 `handle_message` 方法中 `context = retrieve_relevant_context(user_message)` 之前添加：

```python
agent_logger.info("[USER] %s", user_message)
```

- [ ] **Step 4: _agent_loop 添加 LLM 决策日志**

在 `_agent_loop` 中 `lts.log_decision(...)` 调用之前添加：

```python
agent_logger.info("[LLM] 决定调用: %s", ", ".join([tc["name"] for tc in tool_calls]) if tool_calls else "无（直接回复）")
```

- [ ] **Step 5: _agent_loop 添加 LLM 直接回复日志**

在 `_agent_loop` 中 `if not tool_calls:` 分支获取 `final_response` 后添加：

```python
agent_logger.info("[LLM] %s", truncate(final_response))
```

- [ ] **Step 6: _agent_loop 添加工具执行日志**

在 `_agent_loop` 的工具执行循环中（`for tc in tool_calls:` 内部），替换为：

```python
for tc in tool_calls:
    tool = self.tools.get(tc["name"])
    if tool:
        agent_logger.info("[TOOL] %s 开始执行", tc["name"])
        t_start = time.perf_counter()
        try:
            result = await tool.execute(**tc["arguments"])
            elapsed = time.perf_counter() - t_start
            agent_logger.info(
                "[TOOL] %s 完成 (%.1fs): %s",
                tc["name"], elapsed, truncate(result.content),
            )
            outcomes.append(f"[{tc['name']}] {result.content}")
            tool_results.append({
                "tool_name": tc["name"],
                "content": result.content,
                "tool_call_id": tc["id"],
            })
            if result.metadata:
                context += f"\n{tc['name']} 元数据: {result.metadata}"
        except Exception as e:
            elapsed = time.perf_counter() - t_start
            agent_logger.info("[TOOL] %s 失败 (%.1fs): %s", tc["name"], elapsed, str(e))
            raise
```

- [ ] **Step 7: _agent_loop 添加循环结束日志**

在 `self._persist_and_clear()` 之前添加：

```python
agent_logger.info("[SYSTEM] 循环结束 session=%s", self.session_id)
```

- [ ] **Step 8: handle_scheduled 添加定时任务日志**

在 `handle_scheduled` 方法中 `self.short_term.add("system", initial)` 之前添加：

```python
agent_logger.info("[SYSTEM] 定时触发: %s", trigger)
```

- [ ] **Step 9: 提交**

```bash
git add src/core/agent.py
git commit -m "feat: Agent 非流式循环添加日志记录

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: Agent 循环（流式）添加日志

**Files:**
- Modify: `src/core/agent.py`

在 `_agent_loop_stream` 方法中插入日志调用。注意 Task 5 已添加 `import time`、`from src.core.logger import get_logger, truncate` 和模块级 `agent_logger` 实例，此处直接使用。

- [ ] **Step 1: _agent_loop_stream 添加 LLM 决策和回复日志**

在 `_agent_loop_stream` 中，找到 `# 如果没有 tool_calls，直接结束` 那一行，在其上方添加回复日志：

```python
# 如果没有 tool_calls，直接结束
if not tool_calls_buffer:
    if content_buffer:
        agent_logger.info("[LLM] %s", truncate(content_buffer))
        self.short_term.add("assistant", content_buffer)
    yield {"type": "done"}
    return
```

在 `lts.log_decision(...)` 调用之前添加决策日志：

```python
# 记录决策
decision_tool_names = [v["name"] for v in tool_calls_buffer.values()]
agent_logger.info("[LLM] 决定调用: %s", ", ".join(decision_tool_names))
lts.log_decision(
    trigger=trigger,
    tool_calls=decision_tool_names,
    reasoning=content_buffer,
    outcome="",
)
```

- [ ] **Step 2: _agent_loop_stream 添加工具执行日志**

在 `_agent_loop_stream` 的工具执行循环中（`for tc_data in tool_calls_buffer.values():` 内部），在 `result = await tool.execute(**args)` 周围添加耗时记录和日志：

```python
for tc_data in tool_calls_buffer.values():
    name = tc_data["name"]
    yield {"type": "tool_step", "name": name, "status": "running"}

    tool = self.tools.get(name)
    if tool:
        agent_logger.info("[TOOL] %s 开始执行", name)
        t_start = time.perf_counter()
        try:
            args = json.loads(tc_data["arguments"])
            result = await tool.execute(**args)
            elapsed = time.perf_counter() - t_start
            agent_logger.info(
                "[TOOL] %s 完成 (%.1fs): %s",
                name, elapsed, truncate(result.content),
            )
            self.short_term.add_tool_result(
                name, result.content,
                tool_call_id=tc_data["id"],
            )
            if result.metadata:
                context += f"\n{name} 元数据: {result.metadata}"
            yield {"type": "tool_step", "name": name, "status": "done"}
        except (json.JSONDecodeError, Exception) as e:
            elapsed = time.perf_counter() - t_start
            agent_logger.info("[TOOL] %s 失败 (%.1fs): %s", name, elapsed, str(e))
            self.short_term.add_tool_result(
                name, f"执行失败: {e}",
                tool_call_id=tc_data["id"],
            )
            yield {"type": "tool_step", "name": name, "status": "error"}
```

- [ ] **Step 3: 提交**

```bash
git add src/core/agent.py
git commit -m "feat: Agent 流式循环添加日志记录

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: LLM 客户端添加日志

**Files:**
- Modify: `src/core/llm.py`

- [ ] **Step 1: 添加 import 和 logger**

在 `src/core/llm.py` 顶部，在 `from src.core.config import config` 之后添加：

```python
from src.core.logger import get_logger

llm_logger = get_logger("llm")
```

- [ ] **Step 2: `chat()` 方法添加日志**

在 `chat()` 方法中：

在 `for attempt in range(config.LLM_MAX_RETRIES):` 之前添加：

```python
llm_logger.info("[LLM] 调用开始 model=%s", model_name)
```

将 try 块改为记录耗时：

```python
for attempt in range(config.LLM_MAX_RETRIES):
    try:
        t_start = time.perf_counter()
        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = client.chat.completions.create(**kwargs)
        elapsed = time.perf_counter() - t_start
        llm_logger.info("[LLM] 调用完成 (%.1fs)", elapsed)
        # ... 后续处理不变
```

在 `except Exception as e:` 中添加失败日志：

```python
except Exception as e:
    last_error = e
    llm_logger.info("[LLM] 调用失败 (重试 %d/%d): %s", attempt + 1, config.LLM_MAX_RETRIES, str(e))
    if attempt < config.LLM_MAX_RETRIES - 1:
        time.sleep(2 ** attempt)
```

- [ ] **Step 3: `chat_stream()` 方法添加日志**

在 `chat_stream()` 方法中，在重试循环之前添加：

```python
llm_logger.info("[LLM] 流式调用开始 model=%s", model_name)
```

在 `except Exception as e:` 后的重试逻辑中添加失败日志：

```python
except Exception as e:
    last_error = e
    llm_logger.info("[LLM] 流式调用失败 (重试 %d/%d): %s", attempt + 1, config.LLM_MAX_RETRIES, str(e))
    if attempt < config.LLM_MAX_RETRIES - 1:
        time.sleep(2 ** attempt)
```

在流完成后的 else 分支（重试全部失败）不需要改动，因为 `raise RuntimeError` 会由调用方处理。

- [ ] **Step 4: 提交**

```bash
git add src/core/llm.py
git commit -m "feat: LLM 客户端添加调用日志

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: 运行测试并手动验证

**Files:** 无新建/修改

- [ ] **Step 1: 运行全部单元测试**

```bash
pytest tests/ -v
```
期望：所有测试 PASS。

- [ ] **Step 2: 手动启动验证控制台日志**

```bash
python run.py
```
启动后打开浏览器访问 `http://localhost:8000`，发送一条消息，检查控制台是否有 `[USER]`、`[TOOL]`、`[LLM]` 日志输出。

- [ ] **Step 3: 检查日志文件**

```bash
ls -la logs/
cat logs/$(ls -t logs/ | head -1)
```
期望：`logs/` 目录下有日志文件，内容格式与设计文档一致。

- [ ] **Step 4: 验证截断功能**

发送一条会触发较长工具回复的消息（如"分析我的 GitHub 提交"），检查日志文件中工具输出是否正确截断。

- [ ] **Step 5: 验证配置关闭功能**

在 `.env` 中设置 `LOG_TO_CONSOLE=false`，重启服务，确认控制台不再有日志输出，但文件日志正常。

- [ ] **Step 6: 提交（如有变动）**

```bash
git status
```
如有文件变更则提交，否则跳过。
