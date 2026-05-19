# 前端仪表盘设计文档

## 概述

将现有单页聊天界面扩展为多 Tab 仪表盘，让用户可以在前端查看所有已保存的数据：聊天、报告、邮件、记忆、知识图谱、Skills。

**设计原则：** 零新依赖，纯 Vanilla JS + 新增 REST API，在现有 FastAPI + 单 HTML 文件架构上扩展。

## 布局

```
┌──────────────────────────────────────────────┐
│  Header: Evomentor — 个人学习助手    [☰]    │
├─────┬────────────────────────────────────────┤
│     │                                        │
│  收  │         当前 Tab 的内容区               │
│  起  │                                        │
│  时  │                                        │
│  窄  │                                        │
│  条  │                                        │
│     │                                        │
├─────┴────────────────────────────────────────┤
```

- 左侧竖排 Tab 导航，默认收起（仅显示展开按钮），点击展开显示图标 + 文字
- 6 个 Tab：聊天、报告、邮件、记忆、图谱、Skills
- 收起时 Header 显示当前 Tab 名称
- 保持现有深色主题（`#1a1a2e` 背景，`#0f3460` / `#e94560` 强调色）

## API 设计

所有列表接口支持 `?limit=` 和 `?offset=` 分页参数，返回统一格式 `{"items": [...], "total": N}`。

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 保持不变，发送聊天消息 |
| `/api/reports` | GET | 报告列表（GitHub 分析 + 研究报告合并） |
| `/api/reports/{id}` | GET | 报告详情 |
| `/api/reports/{id}` | DELETE | 删除报告 |
| `/api/emails` | GET | 邮件列表，`?status=sent/pending/failed` |
| `/api/emails/{id}` | GET | 邮件详情 |
| `/api/emails/{id}` | DELETE | 删除邮件 |
| `/api/emails/send` | POST | 手动触发发送全部待发邮件 |
| `/api/memories` | GET | 记忆列表，`?type=conversation/experience/decision` |
| `/api/memories/{id}` | DELETE | 删除记忆 |
| `/api/graph` | GET | 知识图谱数据 `{"nodes": [...], "edges": [...]}` |
| `/api/skills` | GET | Skill 列表 |
| `/api/skills/{id}` | GET | Skill 详情，含 Markdown 内容 |
| `/api/skills/{id}` | DELETE | 删除 Skill |
| `/api/reflect` | POST | 手动触发反思 |

## 各 Tab 设计

### 聊天 Tab

保留现有聊天界面（输入框 + 气泡 + Enter 发送），逻辑不变。

### 报告 Tab

- 卡片列表，每张卡片显示：类型标签（GitHub / 研究）、时间、预览文字
- 顶部搜索框 + 类型筛选下拉
- 点击卡片展开完整报告（Markdown 渲染），右上角删除按钮
- 数据来源：`github_analyses` + `research_findings` 表，按时间倒序合并

### 邮件 Tab

- 状态筛选按钮组：全部 / 已发送 / 待发 / 失败
- 卡片列表，状态图标（✅已发送 / ⏳待发 / ❌失败）
- 点击展开 HTML 邮件内容（iframe 渲染）
- 顶部"立即发送全部"按钮，调用 `/api/emails/send`
- 数据来源：`pending_emails` 表

### 记忆 Tab

- 类型筛选：全部 / 对话 / 经验 / 决策
- 关键词搜索框
- 统一卡片列表，不同类型用不同图标/颜色区分
- 点击展开完整内容
- 数据来源：`conversations` + `experiences` + `agent_decisions` 表

### 知识图谱 Tab

- 上半部分：Canvas 力导向布局关系图（节点 + 连线）
- 节点大小/颜色表示掌握程度（1-5）
- 下半部分：知识点列表，每项显示名称 + 熟练度进度条
- 数据来源：`user_knowledge_graph` 表

### Skills Tab

- 卡片列表，显示名称、版本、触发条件、使用次数、成功率
- 点击展开 Markdown 内容（从 `skills/*.md` 文件读取）
- 支持删除
- 数据来源：`skills` 表 + 文件系统

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/web/routes.py` | 重构 | 新增 8 个 API 端点，提取数据查询逻辑 |
| `src/web/templates/index.html` | 重写 | 新增侧边栏 + 5 个 Tab + 分页/搜索/删除交互 |
| `src/web/app.py` | 微调 | 确保静态文件路由正确 |

## 错误处理

- API 错误统一返回 `{"error": "错误描述"}` + 对应 HTTP 状态码
- 前端统一 `try/catch`，错误显示 toast 提示（顶部浮动消失）
- 删除操作弹出确认框，防止误删
- 网络请求失败显示重试按钮

## 实现要点

- 侧边栏动画用 CSS `transition` 实现，不用 JS 动画
- Markdown 渲染用简易正则替换（# 标题、**加粗**、- 列表、链接），不引入 Markdown 库
- 知识图谱用原生 Canvas API 绘制，节点 < 100 时性能足够
- 分页用"加载更多"按钮，不用传统页码
- 所有 API 端点食用现有 `get_connection()` 获取数据库连接
