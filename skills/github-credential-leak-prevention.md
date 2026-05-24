# Skill: github-credential-leak-prevention

## 触发条件
在分析 GitHub 提交历史、当前仓库文件、代码审查或配置文件扫描中，检测到包含硬编码的敏感信息（包括但不限于 Windows 绝对路径、用户名、密码、API 密钥、令牌、本地路径、配置文件占位符等）被提交到版本控制中，或存在于文本文件中。

## 行为规则
## 硬编码敏感信息与凭证泄露检测

### 1. 检测方法
- 扫描所有文本文件（.md, .json, .yml, .py, .sh, .env 等）以及提交历史和仓库内容，使用正则表达式匹配常见敏感信息模式，包括但不限于：
  - **Windows 绝对路径**：`[A-Za-z]:/Users/`、`C:/Users/`、`C:\Users\...`、`C:\Users\w+`。
  - **用户名和占位符**：`<你的用户名>`、`<your-username>`、`<username>`、`<your-home-dir>` 等未替换的占位符。
  - **凭据类**：`password\s*[:=]\s*\S+`、`api[_-]?key\s*[:=]\s*\S+`、`token\s*[:=]\s*\S+`、`api_key=`、`(password|secret|api_key|token)\s*[:=]\s*['"][^'"]+['"]`。
  - **常见敏感信息占位符**：如 `password=`, `api_key=` 等。
- 检查 `.gitignore` 中是否遗漏了常见的敏感文件类型（如 `.env`、`*.key`、`config.local.*`、`settings.json` 等）。
- 标记包含敏感信息的文件路径和具体行号。

### 2. 修复建议
- **立即移除敏感信息**：从版本控制中删除包含敏感信息的文件或内容，强烈推荐使用 `git filter-branch` 或 BFG Repo-Cleaner 清理提交历史（若已提交）。
- **替换为环境变量或相对路径**：
  - 将硬编码的绝对路径替换为相对路径（如 `./data/`）或使用环境变量（如 `%USERPROFILE%`、`$HOME`、`%USERNAME%`）。
  - 将硬编码的敏感信息替换为环境变量或配置文件模板。
- **配置文件模板化**：创建 `.env.example` 或 `config.template.json`，将真实值替换为占位符（如 `<your-home-dir>`），并确保凭据已修改或撤销。
- **更新 `.gitignore`**：添加配置文件路径（如 `settings.json`、`.env`、`*.key`），防止未来提交。
- **使用密钥管理服务**：推荐使用密钥管理服务（如 Vault）或环境变量管理敏感信息。
- **配置自动拦截工具**：配置 `git-secrets`、`pre-commit` 钩子等工具，在提交前自动拦截敏感信息。

### 3. 相关案例
- 用户在 `settings.json` 中硬编码了 Windows 用户名或占位符（如 `<your-username>`），导致个人信息暴露在公开仓库中，需立即清理提交历史并更新凭证。
- 用户项目 'evomentor-agent' 的 README.md 中出现 `C:/User/...` 路径，暴露了开发者用户名和本地文件结构。
- GitHub 提交中 settings.json 硬编码了 Windows 用户名（`<你的用户名>`）。
- 用户最近一次 GitHub 提交中 README.md 包含 `C:/Users/<你的用户名>/`，属于常见新手文档问题。
- 常见错误：在 CI/CD 配置中直接写入本地路径，导致跨平台构建失败。
- 经验 ID 92, 72 均涉及敏感信息提交到版本控制，需确保规则覆盖更全面的敏感信息类型（如密钥、令牌、本地路径、占位符等）。

## 元数据
- 版本: 5
- 创建时间: 2026-05-24T21:50:33.506481
- 来源: 自动合并
