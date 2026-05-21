# 报告文件持久化设计

## 问题

Agent 生成的报告（`agent_report`）仅存储在 SQLite 中，调试不便。需要同时保存为文件。

## 方案

在 `save_agent_report()` 之后，将报告同步写入 `reports/` 目录，Markdown 格式。

## 改动

**文件**：`src/core/agent.py`

- 新增 `_save_report_file()` 辅助函数
- 在两处 `lts.save_agent_report()` 调用后追加文件写入

**文件格式**：
```markdown
# <title>

**触发类型**: periodic_check
**时间**: 2026-05-21 16:30:00
**Session**: abc12345

---

<报告正文>
```

**命名规则**：`reports/YYYY-MM-DD-<trigger>-<session_id>.md`

**Git 提交**：通过 `record_generation()` 登记，循环结束时自动提交

**异常处理**：文件写入失败不阻断 Agent 主流程
