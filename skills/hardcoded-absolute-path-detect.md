# Skill: hardcoded-absolute-path-detect

## 触发条件
当检测到用户提交的代码、配置文件或文档（如 README.md、settings.json、.env、config 文件、脚本等）中包含 Windows 或 Unix 风格的绝对路径（如 C:/Users/...、C:\Users\...、/home/...、/Users/...）且路径中包含用户名、家目录或本地文件结构信息时触发。特别关注路径中是否包含真实用户名（如 john、admin）或占位符（如 <你的用户名>、<username>）。若多次提交反复出现该模式，视为高频风险，应自动触发 Skill。

（新增）当分析用户提交的代码或文档（如 README.md、settings.json）时，检测到包含 Windows 绝对路径模式（如 C:/Users/...、C:\Users\...）

## 行为规则
## 检测方法
1. 扫描所有文本文件（包括代码、配置文件、Markdown 文档、脚本等）内容，匹配常见绝对路径模式：
   - Windows: `[A-Za-z]:\Users\`、`[A-Za-z]:/Users/` 或 `[A-Za-z]:\用户\` 等。
   - Unix: `/home/`、`/Users/`、`/用户/` 等用户家目录前缀。
2. 排除系统环境变量或标准路径（如 `/tmp`、`/var`），仅标记包含疑似用户名或用户目录结构的路径。
3. 使用正则表达式：`([A-Za-z]:\(?:Users|用户)\[^\]+)|(/(?:home|Users|用户)/[^/]+)`
4. 检查路径中是否包含占位符（如 `<你的用户名>`、`<username>`）或真实用户名（如 `john`、`admin`）。
5. 对配置文件（如 settings.json, .env.example, config.yaml）进行重点检查。
6. 如果发现多条经验（如经验 143、138、92、80、72）均指向同一问题，则视为高频模式，应自动触发 Skill。

## 修复建议
1. 使用相对路径（如 `./`、`../`）替代绝对路径，例如 `./data/` 或 `../config/`。
2. 使用环境变量：
   - Windows 下：`%USERPROFILE%`、`%APPDATA%`、`${env:USERPROFILE}`。
   - Unix 下：`$HOME`、`$HOME/.config`，或使用 `~` 代替具体路径。
3. 文档场景（如 README.md）：使用通用占位符（如 `/path/to/your/folder`、`<your-username>`）或提示用户替换路径，而非直接暴露真实路径。
4. 配置文件场景（如 settings.json）：将敏感路径提取到独立的配置文件中，提供模板文件（如 `settings.template.json`、`config.template.json`、`settings.example.json`）并忽略真实配置文件的版本控制。
5. 在 `.gitignore` 中添加敏感文件，防止再次提交。
6. 安全性提醒：不要在版本控制中提交任何包含本地用户目录、系统路径或敏感信息的文件。

## 相关案例
- 用户提交 README.md 中包含 `C:/Users/<你的用户名>/evomentor-agent`，暴露了本地用户名和项目路径。
- 用户 settings.json 中硬编码了 `C:\Users\<你的用户名>\AppData`，导致敏感信息泄露。
- 用户脚本中使用 `/home/username/project/` 作为工作目录，无法在其他机器运行。
- 多次提交中反复出现绝对路径模式（如经验 138、143、92、80、72），表明该用户尚未掌握路径抽象化方法，需要系统提示最佳实践。

（新增）## 1. 检测方法
- 扫描文档和代码中是否包含 `C:/Users/` 或 `C:\Users\` 开头的硬编码绝对路径。
- 检查路径中是否包含个人用户名（如 `<你的用户名>` 或真实用户名）。
- 重点关注 README.md、settings.json、配置文件、脚本文件中的路径字符串。

## 2. 修复建议
- 将硬编码的绝对路径替换为相对路径（如 `./config/`）。
- 使用环境变量（如 `%USERPROFILE%` 或 `$HOME`）替代用户名部分。
- 对于配置文件，建议使用模板文件（如 `.env.example`）并忽略实际配置文件（添加到 `.gitignore`）。
- 示例：将 `C:/Users/你的用户名/project/config` 改为 `./config` 或 `${HOME}/project/config`。

## 3. 相关案例
- 案例1：用户在 README.md 中使用 `C:/Users/<你的用户名>/` 路径，导致文档不可移植且泄露本地结构。
- 案例2：用户在 settings.json 中硬编码 Windows 用户名，提交到 GitHub 后暴露敏感信息。
- 案例3：多个提交中反复出现同一类硬编码路径，表明未形成良好的配置管理习惯。

## 元数据
- 版本: 5
- 创建时间: 2026-05-24T21:57:44.238861
- 来源: 自动合并
