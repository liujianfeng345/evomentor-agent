# Skill: sensitive-info-in-vcs

## 触发条件
当检测到用户将敏感信息（如密码、API密钥、私钥、个人路径、用户名）提交到版本控制系统（如 Git）时。

## 行为规则
## 检测方法
1. 扫描 Git 提交历史中是否包含常见敏感信息模式（如 `password=`, `api_key=`, `secret=`, `-----BEGIN RSA PRIVATE KEY-----` 等）。
2. 检查 `.gitignore` 是否遗漏了常见的敏感文件（如 `.env`, `*.key`, `credentials.json`, `secrets.yml`）。
3. 分析最近提交的文件列表，检查是否有配置文件（如 `settings.json`, `config.ini`, `application.properties`）包含硬编码的敏感值。

## 修复建议
1. 立即从仓库中移除敏感文件：使用 `git rm --cached` 将其从跟踪中移除，并更新 `.gitignore`。
2. 如果敏感信息已被推送到远程，立即轮换所有受影响的密钥/密码，并使用 `git filter-branch` 或 BFG Repo-Cleaner 从历史中清除。
3. 设置预提交钩子（pre-commit hook）自动扫描敏感信息，防止未来再次泄露。
4. 教育团队成员使用环境变量或秘密管理服务（如 AWS Secrets Manager, HashiCorp Vault）来管理敏感信息。

## 相关案例
- 用户在 settings.json 中硬编码了 Windows 用户名（`<你的用户名>`），并提交到 GitHub。
- 用户项目 'evomentor-agent' 的 README.md 中暴露了本地路径和用户名。
- 多个经验（如经验 92、80、72）均指向同一类问题：敏感信息硬编码并提交到版本控制。

## 元数据
- 版本: 2
- 创建时间: 2026-05-21T21:09:38.957828
- 来源: 自动生成
