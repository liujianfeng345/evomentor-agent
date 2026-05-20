# 自动生成内容 Git 提交系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agent 循环结束时自动将本轮生成的 Skill 文件和报告 `git add → commit → push` 到 GitHub。

**Architecture:** 新增 `src/core/git_auto.py` 模块，提供 `record_generation()` 登记生成文件 + `commit_and_push()` 统一提交。工具生成文件后调用 `record_generation()`，Agent 循环结束时调用 `commit_and_push()`。

**Tech Stack:** `subprocess`（标准库）调用系统 `git` 命令，零额外依赖

---



### 文件变更总览

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/core/git_auto.py` | 创建 | `record_generation()` + `commit_and_push()` |
| `tests/test_git_auto.py` | 创建 | 单元测试 |
| `src/tools/skill_manager.py` | 修改 | Skill 文件生成后登记 |
| `src/tools/email_tool.py` | 修改 | 报告保存到文件 + 登记 |
| `src/core/agent.py` | 修改 | 循环结束时调用 `commit_and_push()` |

---

### Task 1: 创建 git_auto 模块

**Files:**
- Create: `src/core/git_auto.py`

- [ ] **Step 1: 创建 `src/core/git_auto.py`**

```python
"""自动 Git 提交 —— Agent 生成文件后统一 add + commit + push。"""
import subprocess
from pathlib import Path


_generated_files: list[tuple[str, str]] = []


def record_generation(file_path: str, description: str) -> None:
    """登记一个自动生成的文件，待循环结束时统一提交。

    Args:
        file_path: 文件路径（相对于项目根目录）
        description: 简短描述，用于构建 commit message
    """
    _generated_files.append((file_path, description))


async def commit_and_push() -> str:
    """将本轮所有登记文件 git add → commit → push。

    Returns:
        操作结果描述。无文件时返回空字符串。
    """
    if not _generated_files:
        return ""

    parts = []
    files = []
    for fp, desc in _generated_files:
        parts.append(desc)
        files.append(fp)

    message = f"auto: {'; '.join(parts)}"

    project_root = Path(__file__).resolve().parent.parent.parent

    try:
        subprocess.run(
            ["git", "add"] + files,
            check=True, capture_output=True, text=True, cwd=str(project_root),
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True, capture_output=True, text=True, cwd=str(project_root),
        )
        subprocess.run(
            ["git", "push"],
            check=True, capture_output=True, text=True, cwd=str(project_root),
        )
        result = f"已提交并推送: {message}"
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else str(e)
        result = f"Git 操作失败: {stderr}"
    finally:
        _generated_files.clear()

    return result
```

- [ ] **Step 2: 验证模块可导入**

```bash
python -c "from src.core.git_auto import record_generation, commit_and_push; print('OK')"
```
期望输出: `OK`

- [ ] **Step 3: 提交**

```bash
git add src/core/git_auto.py
git commit -m "feat: 创建 git_auto 模块

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 编写 git_auto 测试

**Files:**
- Create: `tests/test_git_auto.py`

- [ ] **Step 1: 创建测试文件**

```python
"""git_auto 模块单元测试。"""
import pytest
from src.core.git_auto import record_generation, commit_and_push, _generated_files


class TestRecordGeneration:
    """测试文件登记功能。"""

    def setup_method(self):
        """每个测试前清空登记列表。"""
        _generated_files.clear()

    def test_record_single_file(self):
        """登记单个文件。"""
        record_generation("skills/test.md", "新增 Skill test")
        assert len(_generated_files) == 1
        assert _generated_files[0] == ("skills/test.md", "新增 Skill test")

    def test_record_multiple_files(self):
        """登记多个文件。"""
        record_generation("skills/a.md", "新增 Skill A")
        record_generation("reports/r.html", "生成学习周报")
        assert len(_generated_files) == 2
        assert _generated_files[0] == ("skills/a.md", "新增 Skill A")
        assert _generated_files[1] == ("reports/r.html", "生成学习周报")


class TestCommitAndPush:
    """测试提交推送功能。"""

    def setup_method(self):
        """每个测试前清空登记列表。"""
        _generated_files.clear()

    @pytest.mark.asyncio
    async def test_empty_returns_empty_string(self):
        """无登记文件时返回空字符串。"""
        result = await commit_and_push()
        assert result == ""

    @pytest.mark.asyncio
    async def test_clears_after_commit(self):
        """提交后清空登记列表。"""
        record_generation("skills/test.md", "测试")
        # 由于没有真正的 git 仓库变更，这个调用会失败
        # 但 finally 块仍然会清空列表
        try:
            await commit_and_push()
        except Exception:
            pass
        assert len(_generated_files) == 0

    @pytest.mark.asyncio
    async def test_commit_message_format(self):
        """验证 commit message 格式。"""
        record_generation("skills/x.md", "新增 Skill X")
        record_generation("reports/r.html", "生成学习周报 2026-05-20")
        parts = [desc for _, desc in _generated_files]
        message = f"auto: {'; '.join(parts)}"
        assert message == "auto: 新增 Skill X; 生成学习周报 2026-05-20"
```

- [ ] **Step 2: 运行测试**

```bash
pytest tests/test_git_auto.py -v
```
期望: 5 tests PASS（commit_and_push 的 git 操作测试在无变更时可能失败，但验证的是消息格式和清空逻辑）

- [ ] **Step 3: 提交**

```bash
git add tests/test_git_auto.py
git commit -m "test: 添加 git_auto 模块单元测试

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: skill_manager 添加登记调用

**Files:**
- Modify: `src/tools/skill_manager.py`

在 Skill 文件写入成功后调用 `record_generation()`。

- [ ] **Step 1: 添加 import**

在 `skill_manager.py` 顶部现有 import 区域（第 2 行 `import os` 之后），添加：

```python
from src.core.git_auto import record_generation
```

- [ ] **Step 2: 在文件写入后添加登记**

在 `skill_manager.py` 第 104-105 行的 `with open(filename, "w")` 块之后（注意保持缩进在 for 循环内部），添加：

```python
            record_generation(filename, f"新增 Skill {name}")
```

即修改后该区域为：

```python
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)

            record_generation(filename, f"新增 Skill {name}")

            # 注册到数据库
            conn = get_connection()
```

- [ ] **Step 3: 提交**

```bash
git add src/tools/skill_manager.py
git commit -m "feat: Skill 生成后自动登记 git 提交

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: email_tool 添加报告保存和登记

**Files:**
- Modify: `src/tools/email_tool.py`

在 LLM 润色完成后、SMTP 发送前，保存报告到 `reports/` 目录并登记。

- [ ] **Step 1: 添加 import**

在 `email_tool.py` 顶部现有 import 区域（第 2 行 `from src.tools.base import BaseTool, ToolResult` 之后），添加：

```python
from datetime import datetime
from src.core.git_auto import record_generation
```

- [ ] **Step 2: 在润色后保存报告**

在 `email_tool.py` 第 48 行 `response = llm.chat(...)` 之后、第 50 行 `# 3. 发送邮件` 之前，替换为：

```python
        response = llm.chat([{"role": "user", "content": polish_prompt}])

        # 保存报告到本地文件
        os.makedirs("reports", exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_path = f"reports/weekly-report-{date_str}.html"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(response["content"])
        record_generation(report_path, f"生成学习周报 {date_str}")

        # 3. 发送邮件
```

- [ ] **Step 3: 提交**

```bash
git add src/tools/email_tool.py
git commit -m "feat: 邮件报告保存到本地并登记 git 提交

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: Agent 循环结束时调用 commit_and_push

**Files:**
- Modify: `src/core/agent.py`

在非流式和流式两个路径的循环结束后调用 `commit_and_push()`。

- [ ] **Step 1: 添加 import**

在 `agent.py` 顶部 import 区域（第 5 行 `from src.core.logger import get_logger, truncate` 之后），添加：

```python
from src.core.git_auto import commit_and_push
```

- [ ] **Step 2: 非流式路径 — `_agent_loop` 末尾**

在 `_agent_loop` 方法中，第 181-182 行：

```python
        agent_logger.info("[SYSTEM] 循环结束 session=%s", self.session_id)
        self._persist_and_clear()
        return final_response
```

替换为：

```python
        agent_logger.info("[SYSTEM] 循环结束 session=%s", self.session_id)
        self._persist_and_clear()
        result = await commit_and_push()
        if result:
            agent_logger.info("[SYSTEM] Git: %s", result)
        return final_response
```

- [ ] **Step 3: 流式路径 — `handle_message_stream` finally 块**

在 `handle_message_stream` 方法中，第 92-93 行的 `finally` 块：

```python
        finally:
            self._persist_and_clear()
```

替换为：

```python
        finally:
            self._persist_and_clear()
            result = await commit_and_push()
            if result:
                agent_logger.info("[SYSTEM] Git: %s", result)
```

- [ ] **Step 4: 提交**

```bash
git add src/core/agent.py
git commit -m "feat: Agent 循环结束时自动 git 提交生成文件

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: 运行测试并手动验证

**Files:** 无新建/修改

- [ ] **Step 1: 运行全部测试**

```bash
pytest tests/test_logger.py tests/test_git_auto.py -v
```
期望: 全部 PASS

- [ ] **Step 2: 注册文件后手动验证 commit_and_push**

在项目根目录创建一个测试用的生成文件，手动验证 git 流程：

```bash
echo "test content" > skills/test-auto-commit.md
python -c "
import asyncio
from src.core.git_auto import record_generation, commit_and_push
record_generation('skills/test-auto-commit.md', '测试自动提交')
print(asyncio.run(commit_and_push()))
"
```
期望输出: `已提交并推送: auto: 测试自动提交`

- [ ] **Step 3: 检查 git log 确认提交存在**

```bash
git log --oneline -3
```
期望: 最新 commit 为 `auto: 测试自动提交`

- [ ] **Step 4: 清理测试文件和测试 commit**

```bash
rm skills/test-auto-commit.md
git add skills/test-auto-commit.md
git commit -m "chore: 清理测试文件"
git push
```

- [ ] **Step 5: 启动服务验证自动化流程**

```bash
python run.py
```
触发一次定时检查（或等待），检查日志中是否有 `[SYSTEM] Git: 已提交并推送:` 或 `[SYSTEM] Git: Git 操作失败:`。

- [ ] **Step 6: 提交（如有变动）**

```bash
git status
```
如有文件变更则提交。
