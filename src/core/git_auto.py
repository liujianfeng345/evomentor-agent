"""自动 Git 提交 —— Agent 生成文件后统一 add + commit + push。"""
import subprocess
from pathlib import Path


_generated_files: list[tuple[str, str]] = []


def record_generation(file_path: str, description: str) -> None:
    """登记一个自动生成的文件，待循环结束时统一提交。

    Args:
        file_path: 文件路径（相对于项目根目录）
        description: 简短描述，用于构建 commit message
    """
    _generated_files.append((file_path, description))


async def commit_and_push() -> str:
    """将本轮所有登记文件 git add → commit → push。

    Returns:
        操作结果描述。无文件时返回空字符串。
    """
    if not _generated_files:
        return ""

    parts = []
    files = []
    for fp, desc in _generated_files:
        parts.append(desc)
        files.append(fp)

    message = f"auto: {'; '.join(parts)}"
    project_root = str(Path(__file__).resolve().parent.parent.parent)

    try:
        _run_git(["git", "add"] + files, project_root)

        # 检查是否有暂存变更需要提交
        diff_result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=project_root,
        )
        if diff_result.returncode != 0:
            _run_git(["git", "commit", "-m", message], project_root)
            _run_git(["git", "push"], project_root)
            result = f"已提交并推送: {message}"
        else:
            result = f"文件无变更，跳过提交: {message}"
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="replace").strip() if e.stderr else str(e)
        result = f"Git 操作失败: {stderr}"
    finally:
        _generated_files.clear()

    return result


def _run_git(args: list[str], project_root: str) -> None:
    """执行 git 命令，不捕获文本输出（避免 Windows 编码问题）。"""
    subprocess.run(
        args,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=project_root,
    )
