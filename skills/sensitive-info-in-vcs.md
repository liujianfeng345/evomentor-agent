# Skill: sensitive-info-in-vcs

## 触发条件
Git 提交记录或代码仓库中存在明文敏感信息（如用户名、密码、API 密钥、文件系统路径等）。

## 行为规则
1. **检测方法**：使用正则表达式或预定义规则扫描所有提交的文本文件，查找常见敏感模式（如 `password=`, `api_key=`, `C:/Users/` 等）；可集成 `truffleHog`、`git-secrets` 等工具。
2. **修复建议**：立即从 Git 历史中移除敏感文件（使用 `git filter-branch` 或 BFG Repo-Cleaner），并更新 `.gitignore`；建议使用环境变量或秘密管理服务（如 Vault、GitHub Secrets）存储敏感信息。
3. **相关案例**：用户在 settings.json 中硬编码了 Windows 用户名，并已提交到 GitHub；另一个项目的 README.md 中包含开发者本地路径，暴露了个人信息。

## 元数据
- 版本: 2
- 创建时间: 2026-05-21T23:39:40.621653
- 来源: 自动生成
