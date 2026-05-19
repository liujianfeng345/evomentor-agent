"""GitHub 分析工具 —— 拉取用户 commits 和 Star 仓库动态，分析代码问题。"""
from datetime import datetime, timedelta, timezone
from github import Github, GithubException
from src.tools.base import BaseTool, ToolResult
from src.core.config import config
from src.core.llm import llm
from src.memory.long_term import lts


class GitHubTool(BaseTool):
    name = "github_analyze"
    description = "分析用户最近的 GitHub 提交和 Star 仓库动态，发现代码问题并总结学习点。"

    async def execute(self, days: int = 7) -> ToolResult:
        if not config.GITHUB_TOKEN:
            return ToolResult(success=False, content="GitHub Token 未配置")

        g = Github(config.GITHUB_TOKEN)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        reports: list[str] = []

        try:
            user = g.get_user(config.GITHUB_USERNAME)

            # 1. 分析个人仓库提交
            for repo in user.get_repos():
                if repo.fork:
                    continue
                try:
                    commits = list(repo.get_commits(since=since, author=config.GITHUB_USERNAME))
                    for commit in commits[:20]:
                        analysis = await self._analyze_commit(repo.name, commit)
                        if analysis:
                            reports.append(analysis)
                except (GithubException, IndexError, TypeError):
                    continue

            # 2. 分析 Star 仓库动态
            starred = list(user.get_starred())
            for repo in starred[:10]:
                try:
                    latest_release = repo.get_latest_release()
                    if latest_release.created_at > since:
                        reports.append(
                            f"[Star 仓库更新] {repo.full_name}: "
                            f"最新 Release {latest_release.tag_name} — {latest_release.title}\n"
                            f"{latest_release.body[:300]}"
                        )
                except (GithubException, IndexError, TypeError):
                    continue

        except (GithubException, IndexError, TypeError) as e:
            return ToolResult(success=False, content=f"GitHub API 调用失败: {e.status} - {e.data}")
        finally:
            g.close()

        if not reports:
            return ToolResult(success=True, content="最近没有新的提交或动态。")

        # 汇总分析报告
        full_report = "\n\n---\n\n".join(reports)

        # 交叉对比已有代码模式
        known_patterns = lts.get_experiences_by_category("code_pattern", limit=10)
        if known_patterns:
            full_report += "\n\n## 历史模式提醒\n"
            for p in known_patterns:
                full_report += f"- {p['title']}\n"

        return ToolResult(success=True, content=full_report)

    async def _analyze_commit(self, repo_name: str, commit) -> str:
        """用 LLM 分析单个 commit 的 diff。"""
        files = commit.files
        if not files:
            return ""

        diff_text = ""
        for f in files[:5]:  # 最多分析 5 个文件
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
        return f"## [{repo_name}] {commit.commit.message[:80]}\n{response['content']}"

    def get_parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "分析最近几天的提交，默认 7"},
            },
        }
