import pytest
from unittest.mock import patch, AsyncMock
from src.memory.short_term import ShortTermMemory


@pytest.mark.asyncio
async def test_chat_tool():
    from src.tools.chat import ChatTool
    mem = ShortTermMemory()
    tool = ChatTool(mem)
    result = await tool.execute("什么是 Python 装饰器？")
    assert result.success
    assert result.content
    assert len(mem.get_all()) == 2  # user + assistant


@pytest.mark.asyncio
async def test_github_cache_hit_skips_llm():
    """缓存命中时不应调用 LLM"""
    from unittest.mock import MagicMock
    from src.tools.github import GitHubTool
    from src.memory.long_term import lts

    # 预写入缓存
    from src.db.models import init_db
    init_db()
    lts.save_analysis("cached-repo", "cached-sha", "## 缓存的分析结果")

    tool = GitHubTool()

    # mock Github API 和 LLM —— PyGithub 是同步 API，使用 MagicMock
    with patch("src.tools.github.Github") as mock_gh:
        # 构造假 commit：需要 .sha 属性和 .commit.message 等嵌套属性
        mock_commit = MagicMock()
        mock_commit.sha = "cached-sha"
        mock_commit.commit.message = "test commit"
        mock_commit.commit.author.date = None
        mock_file = MagicMock()
        mock_file.filename = "test.py"
        mock_file.patch = "+print('hello')"
        mock_commit.files = [mock_file]

        mock_repo = MagicMock()
        mock_repo.name = "cached-repo"
        mock_repo.fork = False

        mock_user = MagicMock()
        mock_user.get_repos.return_value = [mock_repo]

        # get_commits 需要在同步上下文中返回列表
        mock_repo.get_commits.return_value = [mock_commit]
        mock_user.get_starred.return_value = []

        mock_gh_instance = MagicMock()
        mock_gh_instance.get_user.return_value = mock_user
        mock_gh.return_value = mock_gh_instance

        with patch("src.tools.github.llm") as mock_llm:
            mock_llm.chat.return_value = {"content": "不应该看到这个"}
            result = await tool.execute(days=7)
            # LLM 不应被调用（缓存命中）
            mock_llm.chat.assert_not_called()
            assert "缓存的分析结果" in result.content
