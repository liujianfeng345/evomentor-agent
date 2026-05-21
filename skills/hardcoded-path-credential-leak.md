# Skill: hardcoded-path-credential-leak

## 触发条件
当检测到用户代码、配置文件（如 settings.json、.env、config.py、config.ini 等）、脚本、README、Markdown 文档或提交内容中包含硬编码的绝对路径（如 C:/Users/...、C:\Users\...、/home/...、/Users/...）或硬编码的用户名、密码、API 密钥等敏感信息时触发。同时检查是否存在 `<你的用户名>`、`<your-username>`、`<username>`、`<YourUserName>` 等占位符但未被替换为实际配置变量或环境变量引用的情况。

## 行为规则
## 1. 检测方法
- 扫描所有文本文件（包括 .md, .json, .yaml, .py, .sh, .env, config.py, settings.json, config.ini 等），查找以 `C:\Users\`、`C:/Users/`、`/Users/`、`/home/` 开头的绝对路径。
- 检查是否有 `<你的用户名>`、`<your-username>`、`<username>`、`<YourUserName>` 等占位符被直接提交，也检查是否包含真实用户名（如 JohnDoe）。
- 使用正则表达式匹配常见用户目录模式：
  - Windows 绝对路径：`[A-Za-z]:\\Users\\[^\\]+`、`[A-Za-z]:/Users/[^/]+` 或通用匹配 `[A-Za-z]:/[^\s"'<>|?*]+`、`[A-Za-z]:\\[^\s"'<>|?*]+`
  - Unix/Linux：`\/home\/[^\/]+` 或 `\/Users\/[^\/]+`
- 检查路径中是否包含常见用户名（如 `Users/\w+`），标记路径中是否出现占位符或真实用户名，确认是否可被他人识别。
- 检测提交历史中是否包含 `.env`、`settings.json`、`config.ini` 等常见配置文件中的敏感信息（如密码、API 密钥）。

## 2. 修复建议
- 将所有绝对路径替换为相对路径或使用环境变量引用，如 `%USERPROFILE%`（Windows）或 `$HOME`、`${env:USERPROFILE}`（Linux/Mac）。
- 创建配置文件模板（如 `settings.json.example`、`config.template.json`、`.env.example`），将实际路径或敏感信息放入 `.gitignore` 中忽略的本地配置文件（如 `settings.json`、`.env`）。
- 在代码中使用 `os.path.expanduser()` 或 `pathlib.Path.home()` 等动态获取用户目录的 API。
- 对于文档中的示例路径，使用占位符（如 `/path/to/your/project`）替代真实路径，避免暴露个人文件夹结构。
- 敏感信息（如用户名、密码、密钥）应使用环境变量、`.env` 文件（并加入 `.gitignore`）或配置管理工具（如 Vault）管理。
- 提交前使用 `.gitignore` 排除包含敏感信息的文件，或使用 `git-secrets`、`truffleHog` 等工具扫描提交。
- 对于已泄露的信息，立即轮换密钥，并从 Git 历史中清除（如使用 `git filter-branch` 或 BFG Repo-Cleaner）。
- 在 .gitignore 中添加本地配置文件排除项（如 `settings.json`、`.env`），防止敏感信息被意外提交。

## 3. 相关案例
- 经验[80]：用户代码中存在 `C:/Users/<你的用户名>` 硬编码路径。
- 经验[72]：settings.json 中硬编码 Windows 用户名，存在路径硬编码与用户名泄露风险。
- 经验[92]：README.md 中硬编码 `C:/Users/<你的用户名>` 导致敏感信息泄露。
- 案例1：用户 `.gitignore` 中未排除 `settings.json`，导致 `C:/Users/JohnDoe/project` 被提交到 GitHub 公共仓库。
- 案例2：用户脚本中写死 `C:/Users/<你的用户名>/data`，在他人电脑上无法运行，且暴露了个人文件夹结构。
- 案例3：用户项目 'evomentor-agent' 的 README.md 中出现 `C:/User/...` 路径，暴露了开发者个人信息和文件结构。
- 高频重复问题：多个经验（ID 92, 80, 72）均涉及 README.md 或 settings.json 中硬编码 `C:/Users/<你的用户名>` 导致敏感信息泄露。
- GitHub 分析指出用户代码中存在 `C:/Users/<你的用户名>` 的硬编码路径。
- 用户在 settings.json 中硬编码了 Windows 用户名（`<你的用户名>`），存在路径硬编码与用户名泄露的风险。

## 元数据
- 版本: 6
- 创建时间: 2026-05-21T21:39:56.431003
- 来源: 自动合并
