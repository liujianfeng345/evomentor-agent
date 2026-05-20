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

    project_root = Path(__file__).resolve().parent.parent.parent

    try:
        subprocess.run(
            ["git", "add"] + files,
            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(project_root),
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(project_root),
        )
        subprocess.run(
            ["git", "push"],
            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(project_root),
        )
        result = f"已提交并推送: {message}"
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else str(e)
        result = f"Git 操作失败: {stderr}"
    finally:
        _generated_files.clear()

    return result
