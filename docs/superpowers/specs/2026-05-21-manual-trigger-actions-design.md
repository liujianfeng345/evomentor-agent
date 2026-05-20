# 手动触发操作面板 设计文档

日期：2026-05-21

## 目标

将定时任务（反思、发邮件、周期检查）暴露为可手动触发的操作，统一收敛到操作面板，支持未来新增操作的扩展性。

## 触发范围

只覆盖现有 3 个定时任务，不做更细粒度的原子操作拆分：

| 操作 | trigger | 描述 |
|---|---|---|
| 周期检查 | `periodic_check` | 分析 GitHub + 研究搜索 + 反思 + 发邮件 |
| 自我反思 | `reflect` | 审视记忆，提炼经验，更新知识图谱 |
| 发送邮件 | `send_email` | 合并队列，LLM 润色后发送 |

## 架构

```
GET /api/actions          → 返回操作列表（前端渲染卡片）
POST /api/actions/stream  → 接收 {trigger}，SSE 流式返回执行过程
```

Agent 新增 `handle_scheduled_stream()` 方法，复用已有 `_agent_loop_stream` 逻辑，上限 8 轮。

## 前端

新增"操作"Tab，侧边栏第 7 项。3 张操作卡片横排，点击后展开流式执行面板，复用聊天 Tab 的 SSE + tool_step 渲染。

## 扩展性

新增操作只需两步：
1. 在 actions 配置中添加条目（名称、trigger、描述、图标）
2. 确保 `handle_scheduled_stream()` 能处理该 trigger

前端自动从 `GET /api/actions` 拉取列表并渲染，无需改动 UI 结构或路由。

## 实现要点

### 后端

- `GET /api/actions` 从 `routes.py` 中定义的 `ACTIONS` 常量读取列表（名称、trigger、描述、图标），作为扩展入口
- `POST /api/actions/stream` 入参 `{trigger: string}`，校验为已知 trigger 后调用 `agent.handle_scheduled_stream(trigger)`
- Agent 的 `prompt_map` 新增 `send_email` 条目，映射对应 prompt
- 现有 `POST /api/emails/send`（走 `handle_message`）改为调用 `handle_scheduled_stream("send_email")`，统一走 scheduled 流式路径；`POST /api/reflect` 同理

### 前端

- 将 `handleSSEEvent` 和 `createStreamingMsg` 中与 Tab 无关的流式渲染逻辑提取为独立 JS 函数，操作 Tab 和聊天 Tab 共享
- 原有 chat Tab 的 SSE 处理不受影响
