# 报告文件持久化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agent 生成报告时除写入 SQLite 外，同步保存 Markdown 文件到 `reports/` 目录。

**Architecture:** 在 `agent.py` 中新增 `_save_report_file()` 辅助函数，在两处 `lts.save_agent_report()` 调用后追加文件写入，通过 `record_generation()` 登记自动 git 提交。

**Tech Stack:** Python, 已有 `record_generation` (git_auto.py)

---

## 文件结构

```
src/core/agent.py  # 修改: 新增 _save_report_file + 两处调用
reports/           # 新建: 报告文件存放目录（首次写入时自动创建）
```

---

### Task 1: 新增报告文件持久化

**Files:**
- Modify: `src/core/agent.py`

- [ ] **Step 1: 添加必要的 import**

在 `agent.py` 顶部已有 import 区域追加：

```python
import os
from datetime import datetime
from src.core.git_auto import record_generation
```

注意：`commit_and_push` 已从 `src.core.git_auto` 导入（第 6 行），`record_generation` 需从同一模块导入。

- [ ] **Step 2: 新增 `_save_report_file` 辅助函数**

在 `Agent` 类定义之前（或之后、类内作为 static method）添加：

```python
def _save_report_file(title: str, content: str, trigger: str, session_id: str) -> None:
    """将报告保存为 Markdown 文件，失败不抛异常。"""
    try:
        os.makedirs("reports", exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_title = title[:50].replace("/", "-").replace("\\", "-")
        filename = f"reports/{date_str}-{trigger}-{session_id}.md"
        body = (
            f"# {title}\n\n"
            f"**触发类型**: {trigger}\n"
            f"**时间**: {datetime.now().isoformat()}\n"
            f"**Session**: {session_id}\n\n"
            f"---\n\n"
            f"{content}"
        )
        with open(filename, "w", encoding="utf-8") as f:
            f.write(body)
        record_generation(filename, f"生成报告: {safe_title}")
    except Exception:
        pass
```

- [ ] **Step 3: 在 `handle_scheduled` 中调用**

找到 `handle_scheduled` 方法（约第 79-90 行），在 `lts.save_agent_report(...)` 之后添加：

```python
                _save_report_file(
                    title=title,
                    content=result.strip(),
                    trigger=trigger,
                    session_id=self.session_id,
                )
```

完整上下文（放在 try 块内，`save_agent_report` 之后）：

```python
        # 保存最终摘要为报告
        if result and result.strip():
            try:
                title = result.strip().split("\n")[0][:80]
                lts.save_agent_report(
                    trigger=trigger,
                    title=title,
                    content=result.strip(),
                    session_id=self.session_id,
                )
                _save_report_file(
                    title=title,
                    content=result.strip(),
                    trigger=trigger,
                    session_id=self.session_id,
                )
            except Exception:
                agent_logger.warning("[SYSTEM] 保存报告失败", exc_info=True)
```

- [ ] **Step 4: 在 `handle_scheduled_stream` 中调用**

找到 `handle_scheduled_stream` 方法（约第 114-125 行），同样在 `lts.save_agent_report(...)` 之后添加 `_save_report_file(...)`：

```python
                elif event["type"] == "done":
                    if text_buffer.strip():
                        try:
                            title = text_buffer.strip().split("\n")[0][:80]
                            lts.save_agent_report(
                                trigger=trigger,
                                title=title,
                                content=text_buffer.strip(),
                                session_id=self.session_id,
                            )
                            _save_report_file(
                                title=title,
                                content=text_buffer.strip(),
                                trigger=trigger,
                                session_id=self.session_id,
                            )
                        except Exception:
                            agent_logger.warning("[SYSTEM] 保存报告失败", exc_info=True)
```

- [ ] **Step 5: 验证**

```bash
python -c "
from src.core.agent import Agent, _save_report_file
import os

# 验证辅助函数可调用
_save_report_file('测试标题', '测试内容', 'periodic_check', 'test123')
print('_save_report_file 调用成功')

# 验证文件已生成
files = os.listdir('reports')
print(f'reports/ 目录文件: {files}')
print('验证通过')
"
```

Expected: 打印调用成功，reports/ 目录有生成的测试文件。

- [ ] **Step 6: 清理测试文件并提交**

```bash
rm reports/$(date +%Y-%m-%d)-periodic_check-test123.md
git add src/core/agent.py
git commit -m "feat: Agent 报告同步保存为 Markdown 文件

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
