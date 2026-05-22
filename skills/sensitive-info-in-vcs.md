# Skill: sensitive-info-in-vcs

## 触发条件
在版本控制系统（如 Git）的提交历史或当前工作区中发现敏感信息（如密码、API 密钥、个人路径、用户名等）

## 行为规则
1. 检测方法：检查 Git 提交历史（通过 `git log -p` 或类似工具）以及当前工作区的文件内容，搜索常见敏感信息模式（如 `password=`, `api_key=`, `C:/Users/`, `ssh-rsa` 等）。
2. 修复建议：立即移除敏感信息，使用 `.gitignore` 忽略包含敏感信息的文件，并重写 Git 历史以彻底清除已泄露的敏感信息（使用 `git filter-branch` 或 `BFG Repo-Cleaner`）。
3. 相关案例：用户在 settings.json 中硬编码了 Windows 用户名，并将该文件提交到了 GitHub；README.md 中包含本地绝对路径和用户名，已暴露在版本控制中。

## 元数据
- 版本: 2
- 创建时间: 2026-05-22T13:53:43.170670
- 来源: 自动生成
