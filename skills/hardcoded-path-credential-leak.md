# Skill: hardcoded-path-credential-leak

## 触发条件
在代码、配置文件或文档中检测到硬编码的绝对路径（如 C:/Users/、/home/username 等）或包含个人用户名的路径。

## 行为规则
## 检测方法
1. 扫描所有文本文件（包括 .md、.json、.yaml、.py、.js 等），查找匹配 `[A-Za-z]:/Users/` 或 `/home/[^/]+` 或 `/Users/[^/]+` 等模式的绝对路径。
2. 检查路径是否包含常见的用户名占位符（如 `<你的用户名>`、`<username>`、`yourname`）或实际用户名。
3. 标记所有包含个人用户目录结构的路径为潜在泄露。

## 修复建议
1. 使用相对路径替代绝对路径，例如将 `C:/Users/你的名字/project/data` 改为 `./data` 或 `../data`。
2. 对于必须使用的路径，改用环境变量（如 `%USERPROFILE%` 或 `$HOME`）或配置文件模板。
3. 将含有真实用户信息的文件添加到 `.gitignore` 中，并提交一份模板文件（如 `config.template.json`）。

## 相关案例
- 经验 [213]、[143]、[138]、[92]、[80]、[72] 均涉及在 README.md、settings.json 等文件中硬编码 Windows 绝对路径并暴露用户名。

## 元数据
- 版本: 2
- 创建时间: 2026-05-26T23:53:25.677044
- 来源: 自动生成
