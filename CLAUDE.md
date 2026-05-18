# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 启动开发服务器
python run.py

# 运行全部测试
pytest tests/ -v

# 运行单个测试文件
pytest tests/test_memory.py -v

# 运行单个测试
pytest tests/test_agent.py::test_agent_chat -v

# 初始化数据库
python -c "from src.db.models import init_db; init_db()"

# 验证配置
python -c "from src.core.config import config; print(config.DEEPSEEK_MODEL)"
```

## 架构概览

Evomentor 是一个基于 **单 Agent 多 Tool** 模式的个人学习助手，运行在 FastAPI + APScheduler 之上。

### Agent 循环（src/core/agent.py）

```
感知 → 思考(LLM) → 行动(Tools) → 观察 → [循环]
```

- **被动触发**：用户通过 Web 发送消息 → `handle_message()` → 最多 5 轮循环
- **主动触发**：调度器唤醒 → `handle_scheduled(trigger)` → 最多 8 轮循环（`periodic_check` / `reflect`）
- 每轮循环：LLM 决定调用哪些 Tool → 执行 Tool → 结果反馈给 LLM → 继续或结束
- 循环结束后持久化对话到 SQLite，**清除短期记忆**（防止残留 tool_calls 污染下次调用）

### 记忆系统

| 层 | 模块 | 存储 | 生命周期 |
|----|------|------|----------|
| 短期 | `src/memory/short_term.py` | 内存列表（50条上限） | 单次 Agent 循环 |
| 长期 | `src/memory/long_term.py` | SQLite（8张表） | 永久 |
| 向量 | `src/db/vector_store.py` | ChromaDB（4个集合） | 永久 |
| 检索 | `src/memory/retrieval.py` | 关键词匹配 + 语义检索 | 每次感知阶段调用 |

`lts`（LongTermMemory）和 `vector_store` 是模块级单例，直接 import 使用。

### 6 个 Tool（src/tools/）

| Tool | 名称 | 用途 |
|------|------|------|
| ChatTool | `chat` | 对话，自动标注话题标签 |
| GitHubTool | `github_analyze` | 分析 commits + Star 仓库动态 |
| EmailTool | `send_email` | 合并队列、LLM 润色、SMTP 发送 |
| ResearchTool | `research` | 搜索 arXiv / HN / GitHub |
| ReflectTool | `reflect` | 审视记忆 + 决策日志 → 提炼经验 → 更新知识图谱 |
| SkillManagerTool | `skill_manager` | 高置信度经验 → Markdown Skill 文件 |

ToolRegistry（`src/tools/__init__.py`）统一注册，提供 OpenAI 兼容的 Tool Schema 给 LLM。

### 自我进化路径

```
对话 / GitHub分析 → ReflectTool 提取经验 → 存入 experiences 表 + 向量库
                   → SkillManagerTool 筛选高置信度经验 → 生成 skills/*.md
```

新 Skill 会被记忆检索加载，注入后续 LLM 调用的 System Prompt。

### 数据层

- **SQLite**（`data/evomentor.db`）：conversations, experiences, skills, github_analyses, research_findings, user_knowledge_graph, agent_decisions, pending_emails
- **ChromaDB**（`data/chroma/`）：conversation_embeddings, experience_embeddings, code_pattern_embeddings, research_embeddings
- ChromaDB 使用内置 embedding 函数（非 DeepSeek embed），`LLMClient.embed()` 方法已定义但当前未被调用

### LLM 调用

- `src/core/llm.py` 通过 OpenAI SDK 调用 DeepSeek API
- 支持 Tool Calling（`tools` + `tool_choice="auto"`）
- 失败自动重试 3 次（指数退避）
- 所有配置从 `.env` 加载（`DEEPSEEK_API_KEY` 必须配置）

### 关键约束

- **Tool Call 消息顺序**：执行 Tool 时先执行获取结果，再写入 short_term（先 assistant tool_calls 后 tool 结果），否则 OpenAI API 报错
- **调度器与 Web 各有一个 Agent 实例**：`scheduler/jobs.py` 和 `web/routes.py` 中各自创建 Agent，互不影响
- **短期记忆每次循环后清除**：`_agent_loop()` 末尾 `self.short_term.clear()` 避免历史 tool_calls 残留
- `.env` 已 gitignore，需从 `.env.example` 复制后手动填写
