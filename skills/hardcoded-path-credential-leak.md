# Skill: hardcoded-path-credential-leak

## 触发条件
当检测到用户提交或修改的代码、配置文件（如 settings.json、.env、config.py、config.ini、*.cfg 等）、脚本、README、Markdown 文档、代码注释或任何文本文件中包含硬编码的 Windows 或 Unix 风格绝对路径时触发。具体检测模式包括：Windows 绝对路径（如 C:/Users/...、C:\Users\...、C:/[^\s"'<>|?*]+、C:\[^\s"'<>|?*]+）、Unix/Linux 绝对路径（如 /home/...、/Users/...、/root/...）以及常见系统目录（如 Program Files、Windows）。同时检查路径中是否包含实际用户名、敏感目录结构、未替换的占位符（如 <你的用户名>、<your-username>、<username>、<YourUserName>、<your-name>、<用户名>、<password>、<your-project-path>、YOUR_USERNAME 等）。此外，检测代码或文档中是否包含硬编码的用户名、密码、API 密钥等敏感信息，并确认占位符是否被直接提交（未被替换为环境变量引用或动态 API 调用）。

## 行为规则
## 1. 检测方法

- **扫描范围**：扫描所有文本文件（包括 .md, .json, .yaml, .py, .sh, .env, config.py, settings.json, config.ini, *.cfg, .env.example, config.template.json, config.yaml 等）及代码注释，使用正则表达式匹配以下模式：
  - Windows 绝对路径：`[A-Za-z]:\\Users\\[^\\]+`、`[A-Za-z]:/Users/[^/]+`、`[A-Za-z]:/[^\s"'<>|?*]+`、`[A-Za-z]:\\[^\s"'<>|?*]+`
  - Unix/Linux 绝对路径：`\/home\/[^\/]+`、`\/Users\/[^\/]+`、`\/root\/[^\/]+`
  - 通用系统目录：`[A-Za-z]:/[Users|Program Files|Windows|...]`

- **检查内容**：
  - 实际用户名（如 JohnDoe、YourName）
  - 未替换的占位符：`<你的用户名>`、`<your-username>`、`<username>`、`<YourUserName>`、`<your-name>`、`<用户名>`、`<password>`、`<your-project-path>`、`YOUR_USERNAME` 等

- **确认占位符是否被直接提交**：检查是否未被替换为环境变量引用（如 `%USERPROFILE%`、`$HOME`、`${env:USERPROFILE}`、`${user.home}`）或动态 API 调用（如 `os.path.expanduser()`、`pathlib.Path.home()`）。

- **历史提交扫描**：对 Git 提交历史进行正则搜索，识别上述模式，特别是 .env、settings.json、config.ini 等常见配置文件中的敏感信息（如密码、API 密钥）。

## 2. 修复建议

- **路径替换**：将所有绝对路径替换为相对路径（如 `./config/`、`./data`、`../data`）或使用环境变量引用，如 `%USERPROFILE%`（Windows）或 `$HOME`、`${env:USERPROFILE}`、`${user.home}`（Linux/Mac）。

- **配置文件模板化**：创建配置文件模板（如 `settings.json.example`、`config.template.json`、`.env.example`、`.env.template`、`config.example.yaml`），将实际路径或敏感信息放入 `.gitignore` 中忽略的本地配置文件（如 `settings.json`、`.env`）。

- **动态路径获取**：在代码中使用 `os.path.expanduser()` 或 `pathlib.Path.home()` 等动态获取用户目录的 API，避免硬编码。

- **文档示例规范**：对于文档中的示例路径，使用通用占位符（如 `/path/to/your/project`、`C:/path/to/your/project`、`<your-project-path>`、`YOUR_USERNAME`）替代真实路径，并添加说明提醒用户自行替换，避免暴露个人文件夹结构。

- **敏感信息管理**：敏感信息（如用户名、密码、密钥）应使用环境变量、`.env` 文件（并加入 `.gitignore`）或配置管理工具（如 Vault）管理。

- **提交前防护**：使用 `.gitignore` 排除包含敏感信息的文件，或使用 `git-secrets`、`truffleHog` 等工具扫描提交。在 .gitignore 中添加本地配置文件排除项（如 `settings.json`、`.env`），防止敏感信息被意外提交。

- **历史泄露补救**：对于已泄露的信息，立即轮换密钥，并从 Git 历史中清除（如使用 `git filter-branch` 或 BFG Repo-Cleaner）。

## 3. 相关案例

- **高频重复问题**：多个经验（ID 143, 138, 92, 80, 72）均涉及 README.md 或 settings.json 中硬编码 `C:/Users/<你的用户名>` 导致敏感信息泄露。
  - 案例1：用户 `.gitignore` 中未排除 `settings.json`，导致 `C:/Users/JohnDoe/project` 被提交到 GitHub 公共仓库。
  - 案例2：用户脚本中写死 `C:/Users/<你的用户名>/data`，在他人电脑上无法运行，且暴露了个人文件夹结构。
  - 案例3：用户项目 'evomentor-agent' 的 README.md 中出现 `C:/User/...` 路径，暴露了开发者个人信息和文件结构。
  - 案例4：用户 settings.json 中硬编码 Windows 用户名，导致敏感信息提交到版本控制。
  - 案例5：GitHub 提交中 README.md 出现硬编码绝对路径。

- **其他典型案例**：
  - 用户多次在 README.md 中使用 `C:/Users/<你的用户名>/` 作为示例路径，导致文档泄露本地目录结构。
  - 用户将 `settings.json` 中的路径硬编码为 `C:/Users/YourName/project/`，提交后暴露了个人用户名。
  - 在脚本中直接写死 `/home/user/project/` 路径，导致其他用户无法直接运行该脚本。

## 元数据
- 版本: 16
- 创建时间: 2026-05-22T23:20:21.013254
- 来源: 自动合并
