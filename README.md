# Evomentor — 自我进化的个人学习助手

一个基于 Agent 架构的个人学习助手，通过 Web 与你交流，定期分析 GitHub 代码、总结对话、探索前沿方向，并以邮件推送学习建议。核心特征是**自我进化**：从每次交互中提炼经验，自动生成可复用的 Skill，持续优化自身行为。

## 功能特性

- **智能对话**：结合记忆上下文提供有深度的技术问答，自动标注话题标签，支持流式 SSE 响应
- **GitHub 代码审查**：分析最近提交的 diff，发现安全漏洞、Bug 模式、代码异味和改进建议
- **前沿方向追踪**：根据你的学习方向搜索 arXiv 论文、Hacker News 讨论和 GitHub 热门仓库
- **网络搜索**：通过 Tavily API 搜索互联网获取最新信息、技术资料和实时数据
- **学习周报邮件**：定期合并对话总结、代码分析和研究方向，LLM 润色后通过 SMTP 发送
- **自我进化**：从对话和代码模式中提炼经验，自动生成可复用的 Skill 规则文件
- **知识图谱**：跟踪你的技术栈熟练度，动态调整建议
- **智能调度**：感知你的活跃状态，在空闲时段触发分析和总结，避免打扰
- **自动版本管理**：生成的报告自动 git commit + push，完整记录学习历程
- **多模型切换**：支持 DeepSeek v4-flash（快速响应）和 v4-pro（深度推理），前端自由切换

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn |
| LLM | DeepSeek（通过 OpenAI SDK），支持多模型注册 |
| 数据库 | SQLite（持久化） + ChromaDB（向量检索） |
| 调度器 | APScheduler |
| 邮件 | aiosmtplib |
| GitHub API | PyGithub |
| 网络搜索 | Tavily API |
| 前端 | 原生 HTML/CSS/JS（深色主题），支持 SSE 流式响应 |

## 快速开始

### 1. 环境准备

```bash
# Python 3.12+
python --version

# 克隆项目
git clone <your-repo-url>
cd evomentor-agent

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env，填写以下必填项：
#   DEEPSEEK_API_KEY  — DeepSeek API 密钥（必填）
#   TAVILY_API_KEY    — Tavily API 密钥（启用网络搜索时需要）
#   GITHUB_TOKEN      — GitHub Personal Access Token（可选，启用代码分析）
#   GITHUB_USERNAME   — GitHub 用户名（可选）
#   SMTP_USER/PASSWORD — 邮件账号（可选，启用邮件推送）
```

### 3. 启动

```bash
python run.py
```

浏览器访问 `http://localhost:8000` 即可开始使用。

## 使用说明

### Web 聊天

在聊天界面输入技术问题，Agent 会根据你的学习背景给出个性化回答。支持**流式 SSE 输出**，回复实时呈现。每次对话结束后，问答会被持久化到数据库。

### 手动操作

前端提供一键触发的操作按钮：
- **周期检查**：分析 GitHub 提交、搜索前沿方向、反思对话、准备学习周报
- **自我反思**：审视近期对话和分析结果，提炼经验，更新知识图谱
- **发送邮件**：合并待发队列中的内容，LLM 润色后发送

所有操作均支持流式输出，实时查看执行进度。

### 自动调度

服务启动后，调度器每 30 分钟检查一次你的活跃状态。当空闲超过 6 小时（可在 `.env` 中配置），自动执行：

1. 拉取 GitHub 最近提交并分析
2. 搜索相关领域的前沿内容
3. 反思近期对话，提炼经验
4. 准备学习周报（待发送）

每 24 小时自动触发一次反思。默认每天发送一封汇总邮件。

### Skill 自动生成

当反思工具发现反复出现的经验模式（如特定的代码问题），Skill 管理工具会将其转化为 `skills/` 目录下的 Markdown 规则文件，后续分析自动引用。

## 项目结构

```
evomentor-agent/
├── run.py                      # 启动入口
├── requirements.txt            # Python 依赖
├── .env.example                # 配置模板
├── src/
│   ├── core/
│   │   ├── agent.py            # Agent 循环（感知→思考→行动→观察），含流式版本
│   │   ├── llm.py              # DeepSeek LLM 客户端（多模型 + 流式）
│   │   ├── config.py           # 配置加载（含模型注册表）
│   │   ├── logger.py           # 日志系统（控制台 + 文件双通道）
│   │   └── git_auto.py         # 自动 Git 提交
│   ├── memory/
│   │   ├── short_term.py       # 短期记忆（内存，50条上限）
│   │   ├── long_term.py        # 长期记忆（SQLite CRUD）
│   │   └── retrieval.py        # 记忆检索（关键词 + 语义）
│   ├── tools/
│   │   ├── base.py             # Tool 基类（BaseTool + ToolResult）
│   │   ├── chat.py             # 对话工具
│   │   ├── github.py           # GitHub 分析工具
│   │   ├── email_tool.py       # 邮件工具
│   │   ├── research.py         # 研究方向工具
│   │   ├── web_search.py       # 网络搜索工具（Tavily API）
│   │   ├── reflect.py          # 反思工具（自我进化核心）
│   │   └── skill_manager.py    # Skill 管理工具
│   ├── scheduler/jobs.py       # 定时任务
│   ├── web/
│   │   ├── app.py              # FastAPI 应用
│   │   ├── routes.py           # API 路由（聊天 / 报告 / 邮件 / 记忆 / 图谱 / Skills）
│   │   ├── static/             # 静态资源（CSS/JS）
│   │   └── templates/          # 前端模板
│   └── db/
│       ├── models.py           # 数据库表定义
│       └── vector_store.py     # ChromaDB 封装
├── skills/                     # 自动生成的 Skill 文件
├── reports/                    # 自动生成的报告文件
├── tests/                      # 测试文件
└── docs/                       # 设计文档与实现计划
```

## 配置说明

`.env` 文件中的所有配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（**必填**） | — |
| `DEEPSEEK_BASE_URL` | API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 默认模型名称 | `deepseek-chat` |
| `DEFAULT_MODEL` | 前端默认选中模型 ID | `deepseek-v4-flash` |
| `TAVILY_API_KEY` | Tavily 搜索 API 密钥 | — |
| `GITHUB_TOKEN` | GitHub Personal Access Token | — |
| `GITHUB_USERNAME` | 要分析的 GitHub 用户名 | — |
| `SMTP_HOST` | SMTP 服务器 | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP 端口 | `587` |
| `SMTP_USER` | 发件邮箱 | — |
| `SMTP_PASSWORD` | 邮箱应用密码 | — |
| `DATABASE_PATH` | SQLite 数据库路径 | `data/evomentor.db` |
| `CHROMA_PATH` | ChromaDB 向量库路径 | `data/chroma` |
| `IDLE_HOURS_BEFORE_TRIGGER` | 空闲多少小时后触发分析 | `6` |
| `LOG_TO_CONSOLE` | 是否输出日志到控制台 | `true` |
| `LOG_TO_FILE` | 是否输出日志到文件 | `true` |
| `LOG_DIR` | 日志文件目录 | `logs` |
| `LOG_TRUNCATE_LENGTH` | 日志截断长度 | `500` |

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 发送消息，返回完整回复 |
| `/api/chat/stream` | POST | 发送消息，SSE 流式返回 |
| `/api/models` | GET | 可用模型列表 |
| `/api/actions` | GET | 可手动触发的操作列表 |
| `/api/actions/stream` | POST | 流式执行操作（SSE） |
| `/api/reports` | GET | 报告列表（合并 GitHub/Research/Agent 报告） |
| `/api/reports/{id}` | GET/DELETE | 报告详情与删除 |
| `/api/emails` | GET | 邮件列表，支持状态筛选 |
| `/api/emails/send` | POST | 手动发送全部待发邮件 |
| `/api/emails/{id}` | GET/DELETE | 邮件详情与删除 |
| `/api/memories` | GET | 记忆列表（合并对话/经验/决策） |
| `/api/memories/{id}` | DELETE | 删除记忆 |
| `/api/graph` | GET | 知识图谱节点和边 |
| `/api/skills` | GET | Skill 列表 |
| `/api/skills/{id}` | GET/DELETE | Skill 详情（含 Markdown 内容）与删除 |
| `/api/reflect` | POST | 手动触发反思 |
| `/api/health` | GET | 健康检查 |

## 测试

```bash
# 运行全部测试
pytest tests/ -v

# 运行单个测试文件
pytest tests/test_agent.py -v

# 运行单个测试
pytest tests/test_agent.py::test_agent_chat -v
```

测试需要配置 `DEEPSEEK_API_KEY` 环境变量（部分涉及 LLM 调用的测试会在 Key 缺失时自动跳过）。

## 部署

项目设计为 7x24 云端运行，推荐部署方式：

```bash
# 使用 nohup 后台运行
nohup python run.py > evomentor.log 2>&1 &

# 或使用 systemd（创建 /etc/systemd/system/evomentor.service）
# 或使用 Docker（自行编写 Dockerfile）
```

部署前确保 `.env` 中所有必填项已配置，`data/` 目录可写。

## 贡献指南

1. 阅读 `docs/superpowers/specs/` 了解设计背景
2. 阅读 `CLAUDE.md` 了解架构约束
3. 遵循现有代码风格（Python 3.12+ 类型注解，异步优先）
4. 新 Tool 继承 `src/tools/base.py` 的 `BaseTool`，在 `ToolRegistry` 中注册
5. 新功能请先在 `docs/superpowers/specs/` 下写设计文档

## 许可证

MIT
