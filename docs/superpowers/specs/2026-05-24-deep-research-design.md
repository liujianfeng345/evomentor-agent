# 深度研究报告功能 设计文档

**日期**: 2026-05-24
**状态**: 待实现

## 1. 功能概述

支持给定一个或多个主题，自动生成深度研究报告。信息来源涵盖论文（arXiv）、GitHub、网络搜索等多种渠道，参考 open_deep_research 框架的多轮迭代研究模式。支持定时触发和手动触发，定时触发自动发送邮件，报告以 Markdown 文件形式保留并自动提交到 GitHub。

## 2. 核心需求

| 维度 | 决定 |
|------|------|
| 研究深度 | 可配置：quick（1轮）/ standard（2轮）/ deep（3轮） |
| 多主题处理 | 每个主题独立生成报告 |
| 主题管理 | 前端界面增删改查，持久化到数据库 |
| 定时策略 | 全局统一调度（默认每24小时） |
| 报告格式 | Markdown 文件存档 + HTML 邮件发送 |
| 信息来源 | 论文（arXiv）、GitHub、网络搜索（Tavily）等 |
| 触发方式 | 手动（API 流式触发）+ 定时（调度器触发） |
| 邮件发送 | 定时触发自动发送，手动触发可选发送 |
| Git 提交 | 报告文件自动 git add + commit + push |

## 3. 架构设计

### 3.1 方案选择：ResearchManager 服务 + Agent 集成

```
触发层
  手动：POST /api/research/stream → Agent → DeepResearchTool
  定时：scheduler → scheduled_research() → ResearchManager

服务层
  ResearchManager（src/research/manager.py）
    ├── run_all() → 批量执行，逐主题串行
    ├── run_single() → 单主题研究管道
    ├── _search_round() → 多源并行搜索
    ├── _analyze() → LLM 分析发现，判断是否继续
    └── _generate_report() → LLM 生成结构化报告

数据层
  research_topics 表（新增）    agent_reports 表（复用）
  reports/*.md 文件（新增）     pending_emails 表（复用）
```

### 3.2 新增文件

| 文件 | 职责 |
|------|------|
| `src/research/__init__.py` | 模块入口 |
| `src/research/manager.py` | ResearchManager 核心，多轮研究管道 |
| `src/tools/deep_research.py` | DeepResearchTool，Agent 可调用的工具封装 |

### 3.3 修改文件

| 文件 | 改动 |
|------|------|
| `src/tools/__init__.py` | 注册 DeepResearchTool |
| `src/scheduler/jobs.py` | 新增 `scheduled_research()` 定时任务 |
| `src/web/routes.py` | 新增主题 CRUD + 研究触发 API |
| `src/db/models.py` | 新增 `research_topics` 表 |
| `src/core/agent.py` | SYSTEM_PROMPT 添加工具说明 |

## 4. 数据模型

### 4.1 新表 research_topics

```sql
CREATE TABLE research_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,              -- 主题名称
    description TEXT,                        -- 可选的描述，帮助 LLM 理解研究方向
    depth TEXT NOT NULL DEFAULT 'standard',  -- quick / standard / deep
    status TEXT NOT NULL DEFAULT 'active',   -- active / paused
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### 4.2 复用表

- `agent_reports`：存储生成的报告（trigger = `scheduled_research` 或 `manual_research`）
- `pending_emails`：邮件待发队列
- `conversations`：对话记录（手动触发时产生）

## 5. API 设计

### 5.1 主题管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/research/topics` | 主题列表 |
| `POST` | `/api/research/topics` | 新增主题 |
| `PUT` | `/api/research/topics/{id}` | 修改主题 |
| `DELETE` | `/api/research/topics/{id}` | 删除主题 |

### 5.2 研究触发

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/research/stream` | 流式触发研究（SSE），body: `{"topic_ids": [1,3]}` 或不传执行全部活跃主题 |
| `GET` | `/api/research/reports` | 研究报告列表（agent_reports 中 trigger 包含 research 的记录） |

### 5.3 SSE 事件类型

| event | 含义 |
|------|------|
| `research_start` | 研究开始，包含主题列表和总数 |
| `topic_start` | 开始处理某个主题 |
| `search_round` | 搜索轮次开始，包含当前轮数和搜索源 |
| `search_done` | 搜索轮次完成，包含本轮的发现数量 |
| `analysis` | LLM 分析结果，包含知识缺口 |
| `report_generating` | 开始生成报告 |
| `report_done` | 报告生成完成，包含文件路径 |
| `research_done` | 全部研究完成 |
| `error` | 异常信息 |

## 6. ResearchManager 核心管道

### 6.1 类结构

```python
class ResearchManager:
    def __init__(self):
        self.tools = ToolRegistry(memory=None)

    async def run_all(self, topic_ids: list[int] | None = None) -> list[str]:
        """批量执行：读取活跃主题，逐主题生成报告"""

    async def run_single(self, topic_id: int) -> str:
        """单主题研究管道 → 返回报告文件路径"""

    async def _research_pipeline(self, topic: dict) -> str:
        """核心管道：多轮搜索 → 分析 → 报告生成"""

    async def _search_round(self, topic: str, context: str) -> str:
        """单轮搜索：并行调用 research + web_search + github_analyze"""

    async def _analyze(self, topic: str, findings: str, round_num: int, depth: str) -> dict:
        """LLM 分析 → {continue: bool, gaps: str, summary: str}"""

    async def _generate_report(self, topic: str, all_findings: str) -> str:
        """LLM 汇总生成 Markdown 报告"""

    def _save_and_enqueue(self, topic_name: str, md_content: str) -> str:
        """保存 .md 文件 + 入邮件队列 + 登记 git 提交"""
```

### 6.2 三种深度模式

| 模式 | 搜索轮数 | 行为 |
|------|----------|------|
| quick | 1 轮 | 并行搜索 3 源 → 直接生成报告 |
| standard | 2 轮 | 广域搜索 → LLM 识别缺口 → 定向补充 → 生成报告 |
| deep | 3 轮 | 广域搜索 → 分析缺口 → 定向深入 → 交叉验证 → 综合报告 |

### 6.3 单主题研究流程（standard 模式示例）

```
1. 并行搜索:
   ResearchTool.execute(topics=["LLM Agent"])
   WebSearchTool.execute(query="LLM agent 2025 2026 latest")
   GitHubTool.execute(action="search")
   → 合并发现文本

2. LLM 分析:
   → {continue: true, gaps: "缺少多Agent通信协议的具体对比"}

3. 定向搜索:
   WebSearchTool.execute(query="multi-agent communication protocol")
   ResearchTool.execute(topics=["multi-agent systems"])

4. LLM 综合分析 + 生成报告:
   # LLM Agent 最新进展研究报告
   ## 1. 概述
   ## 2. 核心发现
   ## 3. 关键项目/论文
   ## 4. 技术趋势
   ## 5. 参考来源
```

## 7. 触发机制

### 7.1 手动触发

- `POST /api/research/stream`，body 可选 `topic_ids`
- SSE 流式返回研究进度
- 每个主题完成后立即保存文件，流式推送给前端

### 7.2 定时触发

- 调度器注册 `scheduled_research` 任务，默认每 24 小时执行
- 从 DB 读取 `status='active'` 的所有主题
- 逐主题串行执行（避免 API 限流）
- 报告生成完毕后自动发送邮件 + Git 提交

### 7.3 Agent 工具集成

- `DeepResearchTool` 注册到 ToolRegistry
- Agent 可在对话中调用 `deep_research` 工具
- 用户可说"帮我研究一下 LLM Agent 的最新进展"

## 8. 邮件与 Git 集成

### 8.1 报告保存

每个主题报告完成后立即执行：
1. 保存 `reports/research-{slug}-{date}.md`
2. `record_generation(file_path)` 登记 Git 提交
3. `lts.save_agent_report()` 存入 agent_reports 表
4. `lts.enqueue_email()` 将 HTML 版报告入邮件队列

### 8.2 邮件发送

- 定时触发：所有主题报告生成后，`EmailTool.execute()` 合并队列发送
- 手动触发：不入邮件队列（或可选项控制）
- HTML 格式：LLM 将 Markdown 转为 HTML 邮件

### 8.3 Git 自动提交

- 复用现有 `commit_and_push()` 机制
- commit message: `auto: 研究报告: {主题1}, {主题2}`
- 在研究流程全部结束后统一提交

## 9. 前端界面

### 9.1 研究主题管理面板

新增"研究主题"管理界面，支持：
- 主题列表展示（名称、深度、状态）
- 新增主题（名称、描述、深度选择）
- 编辑主题
- 删除主题
- 暂停/激活主题
- "立即研究全部"按钮

### 9.2 研究报告列表

复用现有报告列表 UI，按 `trigger='scheduled_research'` 或 `trigger='manual_research'` 筛选，展示报告标题、关联主题、生成时间、支持查看和删除。

### 9.3 研究进度展示

手动触发时，实时展示 SSE 事件流：
- 当前处理的主题
- 搜索轮次进度
- 发现数量
- LLM 分析状态
