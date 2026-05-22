# Skill: sensitive-info-in-vcs

## 触发条件
在版本控制（Git）提交历史或仓库文件中检测到敏感信息（如用户名、密码、API 密钥、本地路径等）被提交。

## 行为规则
1. 检测方法：使用 git log 或文件扫描检查提交内容中是否包含常见敏感信息模式（如 `C:/Users/`、`password=`, `api_key=` 等）。
2. 修复建议：立即移除敏感信息，使用 `.gitignore` 忽略包含敏感信息的文件，并使用 `git filter-branch` 或 `BFG Repo-Cleaner` 清理历史记录。
3. 相关案例：GitHub 提交中暴露了 settings.json 中的 Windows 用户名，属于典型的敏感信息泄露到版本控制的行为。

## 元数据
- 版本: 2
- 创建时间: 2026-05-22T14:20:28.339165
- 来源: 自动生成
