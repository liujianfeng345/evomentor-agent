# Skill: hardcoded-absolute-path-detect

## 触发条件
当分析用户提交的 README.md、配置文件或脚本时，检测到包含 Windows 或 Unix 风格的绝对路径（如 C:/Users/...、/home/...）且路径中包含用户名或本地文件结构信息。

## 行为规则
## 检测方法
1. 扫描文件内容，匹配常见绝对路径模式：
   - Windows: `[A-Za-z]:\\Users\\` 或 `[A-Za-z]:/Users/`
   - Unix: `/home/`、`/Users/` 等用户家目录前缀
2. 排除系统环境变量或标准路径（如 `/tmp`、`/var`），仅标记包含疑似用户名的路径。
3. 使用正则表达式：`([A-Za-z]:\\(?:Users|用户)\\[^\\]+)|(/(?:home|Users|用户)/[^/]+)`

## 修复建议
1. 使用相对路径（如 `./`、`../`）替代绝对路径。
2. 使用环境变量（如 `%USERPROFILE%`、`$HOME`、`${env:USERPROFILE}`）。
3. 对于配置文件，提供模板文件（如 `config.template.json`）并忽略实际文件。
4. 在 `.gitignore` 中添加敏感文件，防止再次提交。

## 相关案例
- 用户提交 README.md 中包含 `C:/Users/<你的用户名>/evomentor-agent`，暴露了本地用户名和项目路径。
- 用户 settings.json 中硬编码了 `C:/Users/<你的用户名>/AppData`，导致敏感信息泄露。
- 用户脚本中使用 `/home/username/project/` 作为工作目录，无法在其他机器运行。

## 元数据
- 版本: 1
- 创建时间: 2026-05-22T17:20:30.854982
- 来源: 自动生成
