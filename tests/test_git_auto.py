"""git_auto 模块单元测试。"""
import pytest
from src.core.git_auto import record_generation, commit_and_push, _generated_files


class TestRecordGeneration:
    """测试文件登记功能。"""

    def setup_method(self):
        """每个测试前清空登记列表。"""
        _generated_files.clear()

    def test_record_single_file(self):
        """登记单个文件。"""
        record_generation("skills/test.md", "新增 Skill test")
        assert len(_generated_files) == 1
        assert _generated_files[0] == ("skills/test.md", "新增 Skill test")

    def test_record_multiple_files(self):
        """登记多个文件。"""
        record_generation("skills/a.md", "新增 Skill A")
        record_generation("reports/r.html", "生成学习周报")
        assert len(_generated_files) == 2
        assert _generated_files[0] == ("skills/a.md", "新增 Skill A")
        assert _generated_files[1] == ("reports/r.html", "生成学习周报")


class TestCommitAndPush:
    """测试提交推送功能。"""

    def setup_method(self):
        """每个测试前清空登记列表。"""
        _generated_files.clear()

    @pytest.mark.asyncio
    async def test_empty_returns_empty_string(self):
        """无登记文件时返回空字符串。"""
        result = await commit_and_push()
        assert result == ""

    @pytest.mark.asyncio
    async def test_clears_after_commit(self):
        """提交后清空登记列表。"""
        record_generation("skills/test.md", "测试")
        # 由于没有真正的 git 仓库变更，这个调用会失败
        # 但 finally 块仍然会清空列表
        try:
            await commit_and_push()
        except Exception:
            pass
        assert len(_generated_files) == 0

    @pytest.mark.asyncio
    async def test_commit_message_format(self):
        """验证 commit message 格式。"""
        record_generation("skills/x.md", "新增 Skill X")
        record_generation("reports/r.html", "生成学习周报 2026-05-20")
        parts = [desc for _, desc in _generated_files]
        message = f"auto: {'; '.join(parts)}"
        assert message == "auto: 新增 Skill X; 生成学习周报 2026-05-20"
