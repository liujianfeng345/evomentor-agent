# Skill: hardcoded-path-credential-leak

## 触发条件
在代码、配置文件或文档中发现硬编码的绝对路径（如 Windows 的 C:/Users/... 或 Linux 的 /home/...）时触发。

## 行为规则
### 1. 检测方法
- 扫描所有文本文件（包括 .md, .json, .yaml, .py, .sh, .conf 等），查找包含 `C:/Users/`、`/home/`、`/Users/` 等绝对路径模式。
- 特别关注用户目录下的路径，例如 `<你的用户名>` 或实际用户名。
- 使用正则表达式 `(C:\\Users\\|/home/|/Users/)[^"'\s]+` 进行匹配。

### 2. 修复建议
- 将硬编码路径替换为通用占位符，如 `%USERPROFILE%` (Windows) 或 `$HOME` (Linux/macOS)。
- 使用环境变量（如 `$HOME`, `$USER`）或配置文件模板（.env.example）来管理路径。
- 确保这些替换后的文件不会泄露个人信息，并且在不同环境下可移植。

### 3. 相关案例
- 用户 [251] 在文档中移除个人绝对路径，替换为通用占位符。
- 用户 [213] 在 claude-pause-chime 项目中修复了文档中的个人绝对路径。
- 用户 [143] 在 README.md 中发现 `C:/Users/<你的用户名>/` 硬编码路径。
- 用户 [138] 在 GitHub 提交中出现了 `C:/Users/<你的用户名>/` 路径。
- 用户 [92] 项目 evomentor-agent 的 README.md 中多次出现 `C:/User/...` 格式路径。
- 用户 [80] 代码中存在 `C:/Users/<你的用户名>` 硬编码路径。
- 用户 [72] 在 settings.json 中硬编码了 Windows 用户名。

## 元数据
- 版本: 2
- 创建时间: 2026-05-27T00:23:24.725095
- 来源: 自动生成
