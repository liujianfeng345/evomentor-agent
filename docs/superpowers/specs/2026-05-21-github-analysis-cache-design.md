# GitHub 提交分析缓存机制

## 背景

GitHubTool 每次执行都会对所有 commit 调用 LLM 分析 diff，即使同一个 commit 从未变过。这导致：
- 重复的 LLM 调用浪费 API 额度
- 多次分析结果可能不一致
- 已存在的 `github_analyses` 表未被使用

## 目标

- 分析过的 commit 不重复调用 LLM
- 缓存 30 天自动过期
- 上限 1000 条，超出淘汰最旧记录
- 数据库异常时降级，不影响主流程

## 设计

### LongTermMemory 新增方法（`src/memory/long_term.py`）

**`get_cached_analysis(repo_name, commit_sha) → dict | None`**
- 查询 `github_analyses` WHERE `repo_name` 和 `commit_sha` 匹配，且 `analyzed_at` 在 30 天内
- 命中返回完整 dict，未命中或过期返回 None

**`save_analysis(repo_name, commit_sha, findings) → int`**
- INSERT 新记录到 `github_analyses`
- findings 为 LLM 返回的完整分析文本
- 返回新记录 id

**`evict_old_analyses(max_keep=1000) → int`**
- 先 DELETE 超过 30 天的记录
- 再 DELETE 超出 max_keep 的最旧记录（保留最新 1000 条）
- 返回删除总数

### GitHubTool 修改（`src/tools/github.py`）

**`_analyze_commit()` 加缓存逻辑**
1. 调用 `lts.get_cached_analysis(repo_name, commit_sha)` 查缓存
2. 命中则直接返回缓存的 findings
3. 未命中则走 LLM 分析，结果非空时调用 `lts.save_analysis()` 写入，然后返回

**`execute()` 末尾加淘汰**
- 在 return 前调用 `lts.evict_old_analyses(max_keep=1000)`

### 边界处理

| 场景 | 处理 |
|------|------|
| 空分析结果（LLM 返回空字符串） | 不缓存 |
| 数据库异常 | 捕获异常，跳过缓存直接走 LLM |
| 同一批次重复分析同一 commit | 第一次 DB 未命中 → LLM → 写入，后续命中 |

## 影响范围

- `src/memory/long_term.py`：新增 3 个方法
- `src/tools/github.py`：修改 `_analyze_commit()` 和 `execute()`
