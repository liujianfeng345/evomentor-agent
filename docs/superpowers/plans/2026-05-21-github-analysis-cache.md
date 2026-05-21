# GitHub 提交分析缓存机制 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 GitHubTool 的 commit LLM 分析增加缓存，避免重复分析相同 commit，30 天过期，上限 1000 条。

**Architecture:** LongTermMemory 新增 3 个方法封装 `github_analyses` 表的 CRUD + 淘汰逻辑，GitHubTool 在 `_analyze_commit` 中先查缓存再决定是否调 LLM。

**Tech Stack:** Python, SQLite (via sqlite3), pytest

---

### Task 1: LongTermMemory 新增缓存方法

**Files:**
- Modify: `src/memory/long_term.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: 编写 LongTermMemory 缓存方法的失败测试**

在 `tests/test_memory.py` 末尾追加：

```python
import time
from src.db.models import init_db


def test_github_analysis_cache_crud():
    """测试 github_analyses 缓存的完整 CRUD 流程"""
    # 确保表已创建
    init_db()

    # 写入一条分析
    analysis_id = lts.save_analysis("test-repo", "abc123", "## 分析结果：代码质量良好")
    assert analysis_id > 0

    # 缓存命中
    cached = lts.get_cached_analysis("test-repo", "abc123")
    assert cached is not None
    assert cached["repo_name"] == "test-repo"
    assert cached["commit_sha"] == "abc123"
    assert cached["findings"] == "## 分析结果：代码质量良好"

    # 不存在的 commit 返回 None
    missing = lts.get_cached_analysis("test-repo", "nonexistent")
    assert missing is None


def test_github_analysis_eviction_count():
    """测试淘汰逻辑：超上限时删除最旧记录"""
    init_db()

    # 写入 5 条记录
    for i in range(5):
        lts.save_analysis("evict-repo", f"sha-{i}", f"findings {i}")
        time.sleep(0.01)  # 确保 created_at 不同

    # 上限设为 3，应删除 2 条最旧的
    deleted = lts.evict_old_analyses(max_keep=3)
    assert deleted >= 2

    # 剩下的应是最新的 3 条
    remaining_ids = []
    for i in range(5):
        c = lts.get_cached_analysis("evict-repo", f"sha-{i}")
        if c:
            remaining_ids.append(i)
    assert remaining_ids == [2, 3, 4]  # sha-0, sha-1 被淘汰


def test_github_analysis_empty_result_not_cached():
    """空分析结果不应写入缓存"""
    init_db()

    result = lts.save_analysis("empty-repo", "empty-sha", "")
    # 空结果返回 0 表示未写入
    assert result == 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_memory.py::test_github_analysis_cache_crud tests/test_memory.py::test_github_analysis_eviction_count tests/test_memory.py::test_github_analysis_empty_result_not_cached -v
```

预期：3 个测试均 FAIL（AttributeError: 'LongTermMemory' object has no attribute 'save_analysis'）

- [ ] **Step 3: 在 LongTermMemory 中实现 get_cached_analysis**

在 `src/memory/long_term.py` 的 `LongTermMemory` 类中，`save_agent_report` 方法之后追加：

```python
    # --- GitHub 分析缓存 ---
    def get_cached_analysis(self, repo_name: str, commit_sha: str) -> dict | None:
        """查询已缓存的 commit 分析结果（30 天内有效）。"""
        conn = get_connection()
        row = conn.execute(
            """SELECT * FROM github_analyses
               WHERE repo_name = ? AND commit_sha = ?
                 AND analyzed_at > datetime('now', '-30 days')
               ORDER BY analyzed_at DESC LIMIT 1""",
            (repo_name, commit_sha),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def save_analysis(self, repo_name: str, commit_sha: str, findings: str) -> int:
        """保存 commit 分析结果到缓存。空 findings 不写入，返回 0。"""
        if not findings.strip():
            return 0
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO github_analyses (repo_name, commit_sha, findings) VALUES (?, ?, ?)",
            (repo_name, commit_sha, findings),
        )
        conn.commit()
        analysis_id = cursor.lastrowid
        conn.close()
        return analysis_id

    def evict_old_analyses(self, max_keep: int = 1000) -> int:
        """淘汰过期和超量的分析缓存。返回删除的总条数。"""
        conn = get_connection()
        deleted = 0

        # 1. 删除超过 30 天的记录
        cursor = conn.execute(
            "DELETE FROM github_analyses WHERE analyzed_at <= datetime('now', '-30 days')"
        )
        deleted += cursor.rowcount

        # 2. 超出上限则删除最旧的
        count = conn.execute("SELECT COUNT(*) FROM github_analyses").fetchone()[0]
        if count > max_keep:
            cursor = conn.execute(
                """DELETE FROM github_analyses WHERE id NOT IN (
                       SELECT id FROM github_analyses ORDER BY analyzed_at DESC LIMIT ?
                   )""",
                (max_keep,),
            )
            deleted += cursor.rowcount

        conn.commit()
        conn.close()
        return deleted
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_memory.py::test_github_analysis_cache_crud tests/test_memory.py::test_github_analysis_eviction_count tests/test_memory.py::test_github_analysis_empty_result_not_cached -v
```

预期：3 个测试 PASS

- [ ] **Step 5: 提交**

```bash
git add src/memory/long_term.py tests/test_memory.py
git commit -m "feat: LongTermMemory 新增 GitHub 分析缓存方法
- get_cached_analysis: 查询 30 天内的缓存分析
- save_analysis: 保存分析结果（空结果不写入）
- evict_old_analyses: 淘汰过期 + 超量记录

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: GitHubTool 集成缓存

**Files:**
- Modify: `src/tools/github.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: 编写 GitHubTool 缓存集成的失败测试**

在 `tests/test_tools.py` 末尾追加：

```python
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_github_cache_hit_skips_llm():
    """缓存命中时不应调用 LLM"""
    from src.tools.github import GitHubTool
    from src.memory.long_term import lts

    # 预写入缓存
    from src.db.models import init_db
    init_db()
    lts.save_analysis("cached-repo", "cached-sha", "## 缓存的分析结果")

    tool = GitHubTool()

    # mock Github API 和 LLM
    with patch("src.tools.github.Github") as mock_gh:
        # 构造一个假 commit
        mock_commit = AsyncMock()
        mock_commit.commit.message = "test commit"
        mock_commit.commit.author.date = None
        mock_commit.files = [AsyncMock()]
        mock_commit.files[0].filename = "test.py"
        mock_commit.files[0].patch = "+print('hello')"

        mock_repo = AsyncMock()
        mock_repo.name = "cached-repo"
        mock_repo.fork = False

        mock_user = AsyncMock()
        mock_user.get_repos.return_value = [mock_repo]
        mock_user.get_starred.return_value = []

        # 设置 get_commits 的返回值（用 lambda 避免迭代问题）
        async def mock_get_commits(**kwargs):
            return [mock_commit]

        async def mock_get_starred():
            return []

        mock_repo.get_commits = mock_get_commits
        mock_user.get_starred = mock_get_starred

        mock_gh_instance = AsyncMock()
        mock_gh_instance.get_user.return_value = mock_user
        mock_gh.return_value = mock_gh_instance

        with patch("src.tools.github.llm") as mock_llm:
            mock_llm.chat.return_value = {"content": "不应该看到这个"}
            result = await tool.execute(days=7)
            # LLM 不应被调用（缓存命中）
            mock_llm.chat.assert_not_called()
            assert "缓存的分析结果" in result.content
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_tools.py::test_github_cache_hit_skips_llm -v
```

预期：FAIL（LLM 仍被调用，缓存逻辑未实现）

- [ ] **Step 3: 修改 GitHubTool._analyze_commit 加缓存逻辑**

修改 `src/tools/github.py` 的 `_analyze_commit` 方法（第 72-104 行），改为：

```python
    async def _analyze_commit(self, repo_name: str, commit) -> str:
        """用 LLM 分析单个 commit 的 diff（优先使用缓存）。"""
        commit_sha = commit.sha

        # 1. 查缓存
        try:
            cached = lts.get_cached_analysis(repo_name, commit_sha)
            if cached and cached.get("findings"):
                return cached["findings"]
        except Exception:
            pass  # 缓存查询失败，降级走 LLM

        files = commit.files
        if not files:
            return ""

        diff_text = ""
        for f in files[:5]:
            patch = f.patch or ""
            diff_text += f"文件: {f.filename}\n{patch[:2000]}\n\n"

        if not diff_text.strip():
            return ""

        prompt = f"""分析以下 Git 提交的代码变更，找出潜在问题：

仓库: {repo_name}
提交: {commit.commit.message[:200]}
时间: {commit.commit.author.date}

代码变更:
{diff_text[:4000]}

请分析：
1. 安全问题（SQL注入、XSS、密钥泄露等）
2. Bug 模式（空指针、并发问题、边界条件等）
3. 代码异味（重复代码、过长函数、命名问题等）
4. 改进建议

用中文回复，简洁直接。"""

        response = llm.chat([{"role": "user", "content": prompt}])
        findings = f"## [{repo_name}] {commit.commit.message[:80]}\n{response['content']}"

        # 2. 写入缓存
        try:
            lts.save_analysis(repo_name, commit_sha, findings)
        except Exception:
            pass  # 缓存写入失败，不影响主流程

        return findings
```

- [ ] **Step 4: 修改 execute() 末尾加淘汰调用**

修改 `src/tools/github.py` 的 `execute` 方法，在 `return` 之前（第 70 行前）插入淘汰调用：

```python
        # 淘汰过期和超量的缓存
        try:
            lts.evict_old_analyses(max_keep=1000)
        except Exception:
            pass

        return ToolResult(success=True, content=full_report)
```

- [ ] **Step 5: 运行缓存集成测试**

```bash
pytest tests/test_tools.py::test_github_cache_hit_skips_llm -v
```

预期：PASS

- [ ] **Step 6: 运行全部 memory 和 tools 测试确保无回归**

```bash
pytest tests/test_memory.py tests/test_tools.py -v
```

预期：全部 PASS

- [ ] **Step 7: 提交**

```bash
git add src/tools/github.py tests/test_tools.py
git commit -m "feat: GitHubTool 集成分析缓存，避免 LLM 重复分析
- _analyze_commit 先查缓存，命中直接返回
- execute 末尾触发淘汰，维持 1000 上限
- 数据库异常降级，不影响主流程

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### 自检清单

- [x] Spec 覆盖：`get_cached_analysis`、`save_analysis`、`evict_old_analyses` 三个方法均已实现（Task 1），GitHubTool 缓存集成（Task 2）
- [x] 无占位符：所有步骤含完整代码和命令
- [x] 类型一致性：方法签名与 spec 一致
