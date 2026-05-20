# 自动生成内容 Git 提交系统设计

## 概述

当 Agent 在定时任务中自动生成 Skill 文件或学习周报时，在 Agent 循环结束时自动执行 `git add → commit → push`，将生成内容推送到 GitHub。

## 模块结构

```
src/core/git_auto.py        ← 新增：文件登记 + 统一 git add/commit/push
src/core/agent.py           ← 修改：循环（非流式+流式）结束时调用 commit_and_push()
src/tools/skill_manager.py  ← 修改：生成 Skill 文件后调用 record_generation()
src/tools/email_tool.py     ← 修改：生成报告后保存到 reports/，调用 record_generation()
```

## `src/core/git_auto.py` 接口

```python
def record_generation(file_path: str, description: str) -> None:
    """登记一个自动生成的文件，待循环结束时统一提交。"""

async def commit_and_push() -> str:
    """将本轮所有登记文件 git add → commit → push。
    返回操作结果描述。无文件时返回 "无文件需提交"。
    """
```

内部实现要点：
- 使用 `subprocess.run` 调用系统 `git` 命令，零额外依赖
- commit message 格式：`auto: <描述1>; <描述2>; ...`
- push 失败静默处理，返回错误信息字符串，不抛异常
- `finally` 中清空登记列表，防止跨循环残留
- 工作目录使用项目根目录（通过 `os.getcwd()` 或相对路径）

## 工具层改动

### `skill_manager.py`

在 `open(filename, "w")` 写入文件成功后，添加：

```python
record_generation(filename, f"新增 Skill {name}")
```

### `email_tool.py`

在 LLM 润色完成后、SMTP 发送之前，保存报告到 `reports/` 目录：

```python
os.makedirs("reports", exist_ok=True)
date_str = <当前日期 YYYY-MM-DD>
report_path = f"reports/weekly-report-{date_str}.html"
with open(report_path, "w", encoding="utf-8") as f:
    f.write(response["content"])
record_generation(report_path, f"生成学习周报 {date_str}")
```

## Agent 层改动

### 非流式路径（`_agent_loop`）

在 `_persist_and_clear()` 之后添加：

```python
result = await commit_and_push()
if result:
    agent_logger.info("[SYSTEM] Git: %s", result)
```

### 流式路径（`handle_message_stream`）

在 `finally` 块的 `_persist_and_clear()` 之后添加：

```python
result = await commit_and_push()
if result:
    agent_logger.info("[SYSTEM] Git: %s", result)
```

## .gitignore 调整

- `skills/` 和 `reports/` 目录不应被忽略（需确认 `.gitignore` 中无相关条目）
- 当前 `.gitignore` 中无 `skills/` 条目，无需修改
- `reports/` 为新目录，不在 `.gitignore` 中，无需修改

## 错误处理

- `skills/` 或 `reports/` 目录不存在时，工具主动创建
- `git push` 失败（网络问题等）→ 记录错误日志，不中断 Agent 流程
- `git commit` 如果没有文件变更 → `subprocess` 会返回错误，需捕获并返回友好信息
- 如果 git 未安装或不在 git 仓库中 → 捕获异常，记录日志

## 日志示例

```
[2026-05-20 14:30:01] [TOOL] skill_manager 完成 (3.2s): 创建了 1 个新 Skill: test-experience-extraction (v1)
[2026-05-20 14:30:05] [TOOL] send_email 完成 (4.5s): 已发送 1 封邮件
[2026-05-20 14:30:05] [SYSTEM] 循环结束 session=abc123
[2026-05-20 14:30:05] [SYSTEM] Git: 已提交并推送: auto: 新增 Skill test-experience-extraction; 生成学习周报 2026-05-20
```

## 后续不做的

- 不处理非自动生成的普通用户文件提交
- 不支持 cherry-pick 特定文件（每轮全部提交）
- 不做提交前的 diff 预览
- 不做 rebase / merge 冲突处理
