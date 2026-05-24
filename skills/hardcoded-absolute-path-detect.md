# Skill: hardcoded-absolute-path-detect

## 触发条件
当检测到用户提交的代码、配置文件或文档（如 README.md、settings.json、脚本等）中包含 Windows 或 Unix 风格的绝对路径（如 C:/Users/...、C:\Users\...、/home/...、/Users/...）且路径中包含用户名、家目录或本地文件结构信息时触发。若多次提交反复出现该模式，视为高频风险，应自动触发 Skill。

## 行为规则
## 检测方法
1. 扫描文件内容，匹配常见绝对路径模式：
   - Windows: `[A-Za-z]:\\Users\\`、`[A-Za-z]:/Users/` 或 `[A-Za-z]:\\用户\\` 等。
   - Unix: `/home/`、`/Users/`、`/用户/` 等用户家目录前缀。
2. 排除系统环境变量或标准路径（如 `/tmp`、`/var`），仅标记包含疑似用户名的路径。
3. 使用正则表达式：`([A-Za-z]:\\(?:Users|用户)\\[^\\]+)|(/(?:home|Users|用户)/[^/]+)`
4. 如果发现多条经验（如经验 143、138、92、80、72）均指向同一问题，则视为高频模式，应自动触发 Skill。

## 修复建议
1. 使用相对路径（如 `./`、`../`）替代绝对路径。
2. 使用环境变量：
   - Windows 下：`%USERPROFILE%`、`%APPDATA%`、`${env:USERPROFILE}`。
   - Unix 下：`$HOME`、`$HOME/.config`。
3. 文档场景（如 README.md）：使用占位符（如 `<your-username>`）或提示用户替换路径，而非直接暴露真实路径。
4. 配置文件场景（如 settings.json）：提供模板文件（如 `settings.template.json`、`config.template.json`）并忽略真实配置文件的版本控制。
5. 在 `.gitignore` 中添加敏感文件，防止再次提交。
6. 安全性提醒：不要在版本控制中提交任何包含本地用户目录、系统路径或敏感信息的文件。

## 相关案例
- 用户提交 README.md 中包含 `C:/Users/<你的用户名>/evomentor-agent`，暴露了本地用户名和项目路径。
- 用户 settings.json 中硬编码了 `C:\Users\<你的用户名>\AppData`，导致敏感信息泄露。
- 用户脚本中使用 `/home/username/project/` 作为工作目录，无法在其他机器运行。
- 多次提交中反复出现绝对路径模式（如经验 138、143、92、80、72），表明该用户尚未掌握路径抽象化方法，需要系统提示最佳实践。

## 元数据
- 版本: 2
- 创建时间: 2026-05-24T18:13:07.247513
- 来源: 自动合并
