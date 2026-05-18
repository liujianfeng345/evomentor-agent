# Evomentor — 个人学习助手 Agent 设计文档

## 概述

Evomentor 是一个能自我进化的个人学习助手 Agent，运行在云端 7x24 小时。它通过 Web 界面与你交互，定期总结对话、分析 GitHub 代码、搜索前沿方向，并以邮件形式推送学习建议。核心特征是 **自我进化**：它从每次交互和分析中提炼经验，自动生成可复用的 Skill，持续优化自身行为。

## 技术选型

| 维度 | 选择 | 原因 |
|------|------|------|
| 语言 | Python 3.12+ | Agent 开发生态最成熟 |
| LLM | DeepSeek（chat 模型） | 成本低，已有 API Key，预留切换接口 |
| Web 框架 | FastAPI | 异步支持好，生态成熟 |
| 数据库 | SQLite | 零运维，个人项目足够 |
| 向量库 | ChromaDB | 轻量，Python 原生 |
| 调度器 | APScheduler | 成熟稳定，支持 cron 和间隔任务 |
| 邮件 | SMTP（aiosmtplib） | 标准协议，支持主流邮箱 |
| GitHub API | PyGithub / httpx | 拉取 commits、stars、仓库信息 |
| Web 搜索 | httpx + 各平台 API | arXiv、Hacker News、Reddit、GitHub Trending |

## 架构总览

```
┌─────────────────────────────────────────┐
│              Web UI (FastAPI)            │
├─────────────────────────────────────────┤
│          调度器 (APScheduler)            │
├─────────────────────────────────────────┤
│       核心 Agent 引擎 (Agent Loop)       │
│                                         │
│  感知 → 思考(LLM) → 行动(Tools) → 观察  │
│                    ↕                     │
│              记忆系统                     │
│         ┌──────┬──────┐                  │
│         │短期记忆│长期记忆│                │
│         └──────┴──────┘                  │
├─────────────────────────────────────────┤
│              工具层 (Tools)              │
│  ┌────┬────┬────┬────┬────┬────────┐    │
│  │聊天│GitHub│邮件│研究│反思│Skill管理│   │
│  └────┴────┴────┴────┴────┴────────┘    │
├─────────────────────────────────────────┤
│           数据层 (SQLite + ChromaDB)     │
└─────────────────────────────────────────┘
```

## 一、核心 Agent 引擎

### Agent 循环

Agent 有两种触发模式：

1. **被动触发**：用户在 Web 发消息 → Agent 执行一次完整的 感知→思考→行动→观察 循环
2. **主动触发**：调度器唤醒 → Agent 执行周期任务（总结对话、分析 GitHub、发送邮件、自我进化）

### 循环流程

```
用户消息 / 定时事件
    ↓
[感知] 加载相关记忆 + 构建当前上下文
    ↓
[思考] LLM 分析 → 决定需要调用哪些 Tool 和顺序
    ↓
[行动] 依次执行 Tool，收集结果
    ↓
[观察] 评估行动结果 → 需要补充行动？→ 回到思考
    ↓
[结束] 更新记忆 → 返回结果给用户 / 存入待发邮件队列
```

### 关键设计

- **单 Agent 多 Tool 模式**：一个 Agent 决策所有 Tool 调用，行为统一，进化能力集中
- **所有 LLM 调用记录决策日志**：为反思和自我进化提供原始素材
- **LLM 调用统一抽象**：`LLMClient` 封装所有 LLM 交互，预留切换模型接口

## 二、记忆系统

### 两层模型

```
短期记忆（对话级）                    长期记忆（持久化）
┌─────────────────────┐          ┌─────────────────────────┐
│ · 当前对话上下文      │  定期    │ · 提炼后的经验教训       │
│ · 最近 GitHub 分析   │ ──────→ │ · 用户偏好 & 习惯建模    │
│ · 本轮 Tool 调用记录  │  总结    │ · 自动生成的 Skills     │
│ · 最近研究结果       │          │ · 代码问题模式库         │
│                     │          │ · 用户知识图谱           │
│ 存储：消息列表(内存)  │          │                         │
│ 生命周期：单次会话    │          │ 存储：SQLite + 向量索引   │
└─────────────────────┘          │ 生命周期：永久            │
                                  └─────────────────────────┘
```

### 短期记忆

- **容量控制**：最多保留最近 50 条消息
- **总结压缩**：超过阈值时自动触发反思 Tool，将对话压缩为摘要存入长期记忆，释放短期空间

### 长期记忆（5 种类型）

| 类型 | 说明 | 存储方式 |
|------|------|----------|
| 经验 | 从对话/GitHub 分析中提炼的教训 | 结构化记录 + 向量 |
| 偏好 | 用户技术栈、风格、习惯 | JSON |
| Skill | 自动生成的可复用行为规则 | Markdown 文件 + DB 注册 |
| 知识图谱 | 用户学习路径和掌握程度 | 图结构（邻接表） |
| 代码模式 | 重复出现的代码问题 | 向量索引 |

### 记忆检索

Agent 在感知阶段做：
1. **关键词匹配**：SQLite 查询相关经验和 Skill
2. **语义检索**：当前上下文向量化，在 ChromaDB 中搜索最相关的历史经验

检索结果注入 LLM 的 System Prompt。

## 三、工具层

### Tool 1：对话工具（chat）

- 接收用户消息，生成回复
- 自动标注话题标签和用户意图
- 问答对写入短期记忆

### Tool 2：GitHub 分析工具（github）

- 拉取指定用户的 commits + diff
- 逐文件分析：安全问题、Bug 模式、代码异味、改进建议
- 拉取 Star 仓库的 README 和最近 release
- 交叉对比已知代码问题模式库
- 输出 Markdown 分析报告

### Tool 3：邮件工具（email）

- 合并多个待发内容为一份邮件
- LLM 润色邮件格式
- 通过 SMTP 发送

### Tool 4：研究工具（research）

- 根据用户当前关注的话题搜索最新资料
- 数据源：arXiv、Papers With Code、Hacker News、Reddit r/MachineLearning、GitHub Trending
- 输出前沿方向摘要和推荐列表

### Tool 5：反思工具（reflect）

自我进化的核心。定期审视短期记忆和决策日志：

- 识别重复出现的问题模式
- 总结有效解决方案
- 更新用户知识图谱
- 判断是否有新经验值得存入长期记忆

### Tool 6：Skill 管理工具（skill_manager）

从反思结果中自动创建和管理 Skill：

- 判断经验是否足够稳定、可复用
- 生成 Skill 模板（名称、触发条件、行为规则）
- 版本化存储为 Markdown 文件
- 跟踪 Skill 的调用次数和成功率

**Skill 格式示例**：
```markdown
# Skill: Django N+1 查询检测
## 触发条件
分析 GitHub 提交时，发现 Django ORM 中在循环内调用 .all()/.get()/.filter()
## 行为
1. 标记该处代码
2. 建议使用 select_related() / prefetch_related()
3. 引用用户之前踩过的坑作为案例
```

## 四、数据层

### SQLite 表结构

**conversations** — 对话记录
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| role | TEXT | user / assistant / system / tool |
| content | TEXT | |
| topic_tags | TEXT(JSON) | 话题标签 |
| intent | TEXT | 用户意图分类 |
| session_id | TEXT | 会话ID |
| created_at | DATETIME | |

**experiences** — 长期经验
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| category | TEXT | code_pattern / learning_tip / user_preference / research_insight |
| title | TEXT | |
| content | TEXT | 详细内容 |
| source | TEXT | 来源（对话ID 或 GitHub分析ID） |
| confidence | REAL | 置信度 0-1 |
| embedding_id | TEXT | ChromaDB 对应 ID |
| created_at | DATETIME | |

**skills** — Skill 注册表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| name | TEXT | Skill 名称 |
| trigger_condition | TEXT | 触发条件 |
| behavior_rules | TEXT(Markdown) | 行为规则 |
| version | INTEGER | |
| active | BOOLEAN | 是否启用 |
| usage_count | INTEGER | 调用次数 |
| success_rate | REAL | 好评率 |
| created_at | DATETIME | |
| updated_at | DATETIME | |

**github_analyses** — 分析历史
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| repo_name | TEXT | 仓库名 |
| commit_sha | TEXT | |
| findings | TEXT(JSON) | 发现的问题列表 |
| suggestions | TEXT | 改进建议 |
| analyzed_at | DATETIME | |

**research_findings** — 研究成果
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| topic | TEXT | 搜索主题 |
| source_type | TEXT | arxiv / reddit / github 等 |
| url | TEXT | |
| summary | TEXT | 摘要 |
| relevance_score | REAL | 相关度 |
| found_at | DATETIME | |

**user_knowledge_graph** — 知识图谱
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| topic | TEXT | 知识领域 |
| proficiency | INTEGER | 掌握程度 1-5 |
| parent_topic | TEXT | 父领域 |
| last_updated | DATETIME | |

**agent_decisions** — 决策日志
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| trigger | TEXT | 触发来源 |
| tool_calls | TEXT(JSON) | 调用了哪些 Tool |
| reasoning | TEXT | LLM 的决策理由 |
| outcome | TEXT | 执行结果 |
| created_at | DATETIME | |

**pending_emails** — 待发邮件队列
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| subject | TEXT | 标题 |
| body | TEXT | HTML 正文 |
| status | TEXT | pending / sent / failed |
| scheduled_at | DATETIME | |
| sent_at | DATETIME | |

### ChromaDB 集合

- `conversation_embeddings` — 对话片段的向量
- `experience_embeddings` — 经验记录的向量
- `code_pattern_embeddings` — 代码模式的向量
- `research_embeddings` — 论文摘要的向量

## 五、调度策略

Agent 根据用户活跃度智能决定任务频率：

- **对话活跃时**：暂不触发主动任务，避免打扰
- **空闲超过 6 小时**：触发一次周期检查（GitHub 分析 + 总结 + 研究）
- **每天至少一次**：即使一直活跃，每天最多发一封邮件
- **邮件合并**：多个待发内容合并为一封，减少打扰

## 六、项目结构

```
evomentor-agent/
├── src/
│   ├── core/               # 核心引擎
│   │   ├── agent.py         # Agent 循环
│   │   ├── llm.py           # LLM 客户端抽象
│   │   └── config.py        # 配置管理
│   ├── memory/              # 记忆系统
│   │   ├── short_term.py    # 短期记忆（内存）
│   │   ├── long_term.py     # 长期记忆（DB）
│   │   └── retrieval.py     # 记忆检索
│   ├── tools/               # 工具层
│   │   ├── base.py          # Tool 基类
│   │   ├── chat.py          # 对话工具
│   │   ├── github.py        # GitHub 分析工具
│   │   ├── email.py         # 邮件工具
│   │   ├── research.py      # 研究工具
│   │   ├── reflect.py       # 反思工具
│   │   └── skill_manager.py # Skill 管理工具
│   ├── scheduler/           # 调度器
│   │   └── jobs.py          # 定时任务定义
│   ├── web/                 # Web 界面
│   │   ├── app.py           # FastAPI 应用
│   │   ├── routes.py        # 路由
│   │   └── templates/       # 前端模板
│   └── db/                  # 数据层
│       ├── models.py        # SQLite 模型
│       ├── vector_store.py  # ChromaDB 封装
│       └── migrations/      # 数据库迁移
├── skills/                  # 自动生成的 Skill 文件
├── docs/                    # 文档
├── requirements.txt
└── .env.example
```

## 七、错误处理与兜底

- **LLM 调用失败**：重试 3 次，仍失败则记录日志，降级处理（跳过该步骤）
- **GitHub API 限流**：缓存结果，增加请求间隔
- **邮件发送失败**：pending_emails 状态标记为 failed，下次调度重试
- **自我进化误判**：自动生成的 Skill 默认 confidence=0.5，需要用户反馈（好评）才能提升到 0.7 以上并主动使用
- **所有关键操作有日志**：便于排查问题和分析 Agent 行为

## 八、后续扩展预留

- LLM 接口支持切换 Claude/GPT 等其他模型
- 数据库可迁移到 PostgreSQL
- 可接入飞书/钉钉/Slack 等 IM 平台
- 可扩展多个用户（目前设计为单用户）
