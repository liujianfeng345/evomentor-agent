# Skill: sensitive-info-in-vcs

## 触发条件
检测到用户提交到版本控制（如 GitHub）的文件中包含或可能包含个人敏感信息，包括但不限于：用户名、密码、API 密钥、令牌、邮箱地址、本地路径结构中的个人标识（如 Windows 用户名）等。

## 行为规则
## 行为规则

### 1. 检测方法
- 扫描文件内容，匹配敏感信息模式：
  - 硬编码的用户名（如 `your-username`、`<你的用户名>`、`<username>`）
  - 密码、令牌、密钥（如 `password=`、`api_key=`、`token=` 等）
  - 邮箱地址（如 `user@example.com`）
  - 绝对路径中的用户名部分（如 `C:/Users/<你的用户名>/`）
- 特别关注配置文件（`.json`、`.yaml`、`.env`、`config.*`、`settings.json`）中的硬编码值
- 结合文件变更历史，标记新增或修改的敏感内容
- 排除公开示例或文档中的占位符（如 `example.com`、`your-username` 需结合上下文判断）
- 检查文件是否属于配置文件且未被 `.gitignore` 忽略

### 2. 修复建议
- 使用环境变量或密钥管理服务（如 AWS Secrets Manager）替代硬编码
- 创建配置文件模板（如 `config.template.json`），将真实配置加入 `.gitignore`
- 在 `.gitignore` 中添加敏感文件（如 `*.env`、`config.local.json`）
- 使用 `.gitattributes` 标记敏感文件为 `export-ignore`
- 对于已提交的敏感信息：
  - 立即撤销提交并轮换密钥
  - 使用 `git filter-branch` 或 `BFG Repo-Cleaner` 清理历史记录
- 提醒用户定期审查提交内容，开启 GitHub 的 Secret Scanning 功能

### 3. 相关案例
- 用户提交的 README.md 中包含 `C:/Users/<你的用户名>/`，暴露了本地用户名
- 用户提交的 `settings.json` 中硬编码了 Windows 用户名，导致路径泄露
- 用户提交的 `.env` 文件中包含数据库密码，未加入 `.gitignore`
- 用户将数据库连接字符串（含密码）直接写在代码中并提交，造成安全风险

## 元数据
- 版本: 2
- 创建时间: 2026-05-22T17:20:36.433721
- 来源: 自动合并
