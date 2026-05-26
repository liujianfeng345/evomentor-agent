# Skill: hardcoded-absolute-path-detect

## 触发条件
当检测到用户提交的代码、配置文件或文档（如 README.md、settings.json、.env、config 文件、脚本等）中包含 Windows 或 Unix 风格的绝对路径（如 C:/Users/...、C:\Users\...、/home/...、/Users/...、/root/...）且路径中包含用户名、家目录或本地文件结构信息时触发。特别关注路径中是否包含真实用户名（如 john、admin）或占位符（如 <你的用户名>、<username>、<user>、YourName）以及类似占位符但实际为硬编码用户名的情况。若多次提交反复出现该模式（如经验 213、143、138、92、80、72），视为高频风险，应自动触发 Skill。同时，检查是否有 .gitignore 或 .env 文件缺失，导致敏感文件可能被提交。

## 行为规则
# 硬编码路径与敏感信息泄露检测

## 1. 检测方法
- **正则匹配**：扫描所有文本文件（包括代码、配置文件、Markdown 文档、脚本等）内容，查找以下模式：
  - Windows 绝对路径：`[A-Za-z]:\Users\`、`[A-Za-z]:/Users/`、`[A-Za-z]:\用户\` 或 `[A-Za-z]:/用户/`，以及以盘符（如 `C:/`、`D:/`）开头的绝对路径。
  - Unix/Linux/macOS 绝对路径：`/home/[^/]+`、`/Users/`、`/用户/`、`/root/` 等用户家目录前缀。
- **上下文分析**：检查路径中是否包含疑似用户名、用户目录名或占位符（如 `<你的用户名>`、`<username>`、`<user>`、`YourName`），以及类似占位符但实际为硬编码用户名的情况，这些是硬编码路径的典型特征。
- **重点检查对象**：对配置文件（如 settings.json、.env.example、config.yaml）、Markdown 文档（如 README.md）以及脚本文件进行重点检查。
- **高频模式判定**：如果发现多条经验（如经验 213、143、138、92、80、72）均指向同一问题，则视为高频模式，应自动触发 Skill。
- **排除项**：排除系统环境变量或标准路径（如 `/tmp`、`/var`），仅标记包含疑似用户名或用户目录结构的路径。
- **额外检查**：检查是否有 `.gitignore` 或 `.env` 文件缺失，导致敏感文件（如包含硬编码路径的配置文件）可能被提交。

## 2. 修复建议
- **使用相对路径**：将 `C:/Users/YourName/Project/config.ini` 改为 `./config.ini` 或 `../config.ini`，确保路径可移植。
- **使用环境变量**：
  - Windows 下：使用 `%USERPROFILE%`、`%APPDATA%`、`${env:USERPROFILE}` 替代用户名部分。
  - Unix/macOS 下：使用 `$HOME`、`$HOME/.config`，或使用 `~` 代替具体路径。
- **使用配置文件模板**：
  - 将敏感路径提取到独立的配置文件中，提供模板文件（如 `settings.template.json`、`config.template.json`、`config.template.ini`、`.env.example`），其中路径使用占位符（如 `PATH_TO_DATA = <your_data_path>`）。
  - 将实际配置文件（如 `config.ini`、`settings.json`）添加到 `.gitignore` 中，防止再次提交。
- **文档场景**（如 README.md）：使用通用占位符（如 `/path/to/your/folder`、`<your-username>`）并说明用户需替换，而非直接暴露真实路径。
- **代码场景**：在代码中使用 `os.path.join()` 或 `pathlib.Path` 来构建路径，避免字符串拼接；建议使用 `pathlib` 或 `os.path` 构建跨平台路径。
- **安全性提醒**：不要在版本控制中提交任何包含本地用户目录、系统路径或敏感信息的文件。

## 3. 相关案例
- **案例 1 (README.md 文档)**：用户提交的 README.md 中包含 `C:/Users/<你的用户名>/evomentor-agent` 或 `C:/Users/<你的用户名>/project/run.sh`，暴露了本地用户名和项目路径。建议改为 `./run.sh`、`bash run.sh` 或使用占位符 `/path/to/your/folder`。
- **案例 2 (settings.json 配置文件)**：用户提交的 settings.json 中硬编码了 `C:\Users\<你的用户名>\AppData` 或 `"pythonPath": "C:/Users/YourName/AppData/Local/Programs/Python/Python39/python.exe"`，导致敏感信息泄露。建议移除该配置或使用环境变量 `"pythonPath": "${env:PYTHON_PATH}"`。
- **案例 3 (Shell 脚本)**：用户提交的 `.sh` 文件中包含 `cd /home/user/project` 或 `cd /home/username/project/`，在其他机器上无法运行。建议改为 `cd $(dirname "$0")` 或使用相对路径 `cd ../project`。
- **案例 4 (高频模式)**：多个提交中反复出现绝对路径模式（如经验 213、143、138、92、80、72），表明该用户尚未掌握路径抽象化方法，需要系统提示最佳实践。
- **案例 5 (配置文件缺失)**：用户提交了包含硬编码路径的 `settings.json`，但缺少 `.gitignore` 和模板文件，导致敏感信息泄露风险。建议创建 `.gitignore` 忽略配置文件，并提供 `config.example.json` 模板。

## 元数据
- 版本: 13
- 创建时间: 2026-05-26T22:54:13.993162
- 来源: 自动合并
