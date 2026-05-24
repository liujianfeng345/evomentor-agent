# Skill: hardcoded-absolute-path-detect

## 触发条件
检测到用户代码、配置文件或文档中包含以 `C:/Users/` 开头的 Windows 绝对路径，或类似形式的绝对路径（如 `/home/username/`）时触发。

## 行为规则
### 1. 检测方法
- 扫描所有文本文件（包括 .md, .json, .py, .yaml, .env 等）中的字符串，匹配模式：`[A-Za-z]:/Users/[^/]+` 或 `/home/[^/]+` 或 `/Users/[^/]+`。
- 特别关注 README.md、settings.json、config.yaml、docker-compose.yml 等常见文件。
- 如果路径中包含 `用户名`、`<你的用户名>` 或类似占位符，也视为硬编码路径。

### 2. 修复建议
- 建议使用相对路径（如 `./config/`）替代绝对路径。
- 建议使用环境变量（如 `%USERPROFILE%` 或 `$HOME`）或配置文件模板（如 `.env.example`）来动态获取用户目录。
- 对已提交到版本控制的历史记录，建议使用 `git filter-branch` 或 `BFG Repo-Cleaner` 清理敏感路径。

### 3. 相关案例
- 用户曾在 README.md 中写入 `C:/Users/<你的用户名>/projects/`，导致目录结构泄露。
- 用户在 settings.json 中硬编码了 `C:/Users/小明/AppData/...`，暴露了真实用户名。
- 该问题在多个经验中重复出现（经验 ID: 143, 138, 92, 80, 72），属于高频典型错误。

## 元数据
- 版本: 2
- 创建时间: 2026-05-25T01:22:21.419373
- 来源: 自动生成
