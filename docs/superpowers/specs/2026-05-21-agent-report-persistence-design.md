# Agent 报告自动持久化 设计文档

日期：2026-05-21

## 目标

Agent 执行 `periodic_check` 等定时触发任务后，将最终输出的学习周报摘要自动保存到数据库，前端报告 Tab 可查看。

## 现状问题

Agent 多轮循环的最后一段文本（周报总结）仅在流式面板闪现，未持久化。`github_analyses` 和 `research_findings` 两张表有建表语句但无写入代码。

## 持久化时机

`handle_scheduled_stream` 中累积 text 事件到 buffer，出现 `tool_start` 时清空（说明 LLM 仍在执行工具而非输出最终总结）。收到 `done` 事件时若 buffer 非空，则保存为报告。

## 数据表

新增 `agent_reports` 表：

```sql
CREATE TABLE IF NOT EXISTS agent_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    session_id TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 改动

| 文件 | 改动 |
|------|------|
| `src/db/models.py` | SCHEMA 新增 `agent_reports` 表 |
| `src/memory/long_term.py` | 新增 `save_agent_report()` 方法 |
| `src/core/agent.py` | `handle_scheduled_stream` 累积 text，done 时保存 |
| `src/web/routes.py` | `/api/reports` 增加 `agent_report` 类型 |
| `src/web/templates/index.html` | 报告 Tab 筛选下拉 + 渲染 |

## API 兼容

`GET /api/reports?type=agent_report` 新增，`type=` 或 `type=github|research` 行为不变。
