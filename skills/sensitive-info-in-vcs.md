# Skill: sensitive-info-in-vcs

## 触发条件
当分析用户提交的版本控制系统（如 Git）变更时，检测到文件（包括但不限于 README.md、配置文件如 .json、.yaml、.env、.ini、.cfg、config.*、settings.*，以及代码文件）中包含或可能包含硬编码的绝对路径（如 Windows 路径 C:/Users/、Unix 路径 /home/）或敏感信息（如用户名、密码、API 密钥、令牌、邮箱地址、电话号码等个人身份信息）。重点关注新增或修改的 diff 内容、提交历史中的文件变更，以及配置文件和文档中的硬编码值。特别关注初次提交或仅包含文档的提交。

## 行为规则
## 1. 检测方法
- 扫描仓库中所有非二进制文件（特别是 .json、.yaml、.env、.ini、.cfg、.txt、.md 文件），匹配敏感信息模式：
  - 硬编码的绝对路径：`[A-Za-z]:\\Users\\[^\\]+`、`/home/[^/]+`、`C:/Users/[^/]+` 等，包括包含用户名占位符（如 `<你的用户名>`、`your-username`）的路径
  - 硬编码的用户名（如 `your-username`、`<你的用户名>`、`<username>`）
  - 注释或文档中包含开发者的真实用户名或机器名
  - 密码、令牌、密钥（如 `password=`、`api_key=`、`token=`、`secret=` 等）
  - 邮箱地址（如 `user@example.com`）
  - 电话号码等个人身份信息
- 特别关注配置文件（`.json`、`.yaml`、`.env`、`config.*`、`settings.json`、`settings.*`）和文档（如 `README.md`、`*.md`）中的硬编码值
- 检查最近提交的 diff 中新增或修改的敏感内容，结合文件变更历史进行标记
- 若提交内容仅为文档且包含敏感信息，标记为“文档级敏感泄露”
- 排除公开示例或文档中的占位符（如 `example.com`、`your-username` 需结合上下文判断；已知测试或示例文件如 `example.env` 中的占位符应忽略）
- 检查文件是否属于配置文件且未被 `.gitignore` 忽略

## 2. 修复建议
- 使用环境变量或密钥管理服务（如 AWS Secrets Manager）替代硬编码，在代码中引用环境变量
- 使用相对路径替代绝对路径，例如将 `C:/Users/Alice/project/data/` 改为 `./data/` 或 `../data/`
- 使用环境变量替代用户目录部分，例如 `$HOME/data/` 或 `%USERPROFILE%\data\`
- 创建配置文件模板（如 `config.template.json`、`.env.example`、`config.example.json`），将真实配置加入 `.gitignore`
- 对于需要保留模板的情况，使用占位符（如 `<你的用户名>`）并在文档中说明用户需要自行替换
- 在 `.gitignore` 中添加敏感文件（如 `*.env`、`config.local.json`、`settings.json` 本身，只提交模板文件、`*.local.*`）
- 使用 `.gitattributes` 标记敏感文件为 `export-ignore`
- 对于已提交的敏感信息：
  - 立即撤销提交并轮换密钥
  - 使用 `git filter-branch` 或 `BFG Repo-Cleaner` 清理 Git 历史
- 提醒用户定期审查提交内容，开启 GitHub 的 Secret Scanning 功能
- 建议用户启用 Git 预提交钩子（如 `git-secrets`）自动检测敏感信息，并使用 `git diff` 或预提交钩子检查是否包含绝对路径或个人标识，防止未来再次提交

## 3. 相关案例
- 用户提交的 README.md 中包含 `C:/Users/<你的用户名>/`，暴露了本地用户名
- 用户提交的 `settings.json` 中硬编码了 Windows 用户名，导致路径泄露
- 用户提交的 `.env` 文件中包含数据库密码，未加入 `.gitignore`
- 用户将数据库连接字符串（含密码）直接写在代码中并提交，造成安全风险
- 经验 [92]、[72]、[143]、[138]、[80] 多次出现硬编码绝对路径问题，属于敏感信息泄露模式，尤其是在 settings.json 和 README.md 中重复出现
- 经验 [138]：仅包含 README.md 的提交中出现了硬编码绝对路径
- 此类问题常见于新手将本地开发路径直接写入文档或配置文件，导致仓库克隆后路径失效，并可能泄露本地文件结构信息

## 元数据
- 版本: 7
- 创建时间: 2026-05-24T17:57:57.462471
- 来源: 自动合并
