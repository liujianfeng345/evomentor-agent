# Skill: sensitive-info-in-vcs

## 触发条件
在 Git 提交历史或仓库文件中发现敏感信息（如用户名、密码、API 密钥、本地路径等）

## 行为规则
1. 检测方法：使用正则表达式扫描所有提交文件，匹配常见敏感信息模式（如 `C:/Users/`, `password=`, `api_key=`, `token=` 等）；检查 `.gitignore` 是否遗漏了敏感文件。
2. 修复建议：使用 `git filter-branch` 或 BFG Repo-Cleaner 从历史中移除敏感信息；添加 `.gitignore` 规则排除配置文件；启用 Git 钩子（pre-commit）自动检测敏感信息。
3. 相关案例：用户提交中 settings.json 包含了硬编码用户名，导致敏感信息暴露在版本控制中；另一案例中 README.md 包含本地绝对路径，属于常见泄露模式。

## 元数据
- 版本: 2
- 创建时间: 2026-05-22T16:20:09.108444
- 来源: 自动生成
