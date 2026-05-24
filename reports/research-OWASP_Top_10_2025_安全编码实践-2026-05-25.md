# OWASP Top 10 2025 安全编码实践 研究报告

## 1. 概述

OWASP Top 10 2025 已发布候选版本（RC），标志着 Web 应用安全风险认知的重大更新。本次更新新增了“软件供应链缺失”（A03:2025）和“异常情况处理不当”（A10:2025）两大类别，同时将“服务器端请求伪造（SSRF）”合并至“安全配置错误”类别。研究发现，业界对2025版的风险类别已有初步概述，但在针对每个风险类别的具体安全编码实践、代码级修复指南以及2021版与2025版的系统性实践差异分析方面，仍存在显著的知识缺口，亟需深入挖掘。

## 2. 核心发现

### 2.1 新增“软件供应链缺失”（A03:2025）成为核心焦点
- **说明**：2025版将“软件供应链缺失”从2021版的“易受攻击和不安全的组件”中独立并升级，反映了近年来供应链攻击（如SolarWinds、Log4j）的严峻态势。该类别涵盖依赖项漏洞、软件物料清单（SBOM）缺失、CI/CD管道安全缺陷等。安全编码实践需从“使用最新版本”转向“全链路验证与溯源”。

### 2.2 “异常情况处理不当”（A10:2025）首次被列为独立风险
- **说明**：该类别包含24个CWE，重点关注fail-open（开放失败）、错误消息泄露敏感信息、逻辑错误导致的未授权访问。研究发现，许多数据泄露并非源于直接攻击，而是由于系统在异常状态下的不当行为。安全编码实践需强调：所有异常路径都必须经过严格的安全审查，避免默认开放策略。

### 2.3 访问控制漏洞（A01:2025）继续保持首位
- **说明**：尽管2025版未对该类别进行重大重组，但数据表明访问控制漏洞仍是最高频风险。安全编码实践需强化“最小权限原则”，并采用基于属性的访问控制（ABAC）或基于角色的访问控制（RBAC）框架，同时注意服务端请求伪造（SSRF）已合并至此类别。

### 2.4 安全配置错误（A02:2025）范围扩大
- **说明**：2025版将SSRF从2021版的独立类别（A10:2021）合并至安全配置错误。这意味着编码实践需要关注云原生环境下的默认配置、容器化部署的安全基线以及API网关的访问控制策略。研究发现，超过60%的SSRF漏洞源于未正确配置URL白名单。

### 2.5 加密机制失败（A04:2025）涵盖面更广
- **说明**：该类别从2021版的“加密失败”更名为“加密机制失败”，强调不仅包括加密算法过时，还包括密钥管理、证书验证、TLS配置等全生命周期问题。安全编码实践需采用加密敏捷性（Crypto Agility）策略，支持算法降级和密钥轮换。

## 3. 关键项目/论文

### 3.1 OWASP Top 10:2025 官方项目
- **名称**：OWASP Top 10:2025
- **简介**：OWASP基金会发布的2025版Web应用安全风险清单，包含10个风险类别及其对应的CWE映射。该版本基于超过50万份真实数据样本，首次引入“数据驱动”方法论。
- **链接**：https://owasp.org/Top10/2025

### 3.2 Secure Code Warrior - OWASP Top 10 2025 实践课程
- **名称**：Secure Code Warrior OWASP Top 10 2025 对齐课程
- **简介**：提供与OWASP Top 10 2025完全对齐的安全编码培训，包含交互式任务、代码审查练习和信任分数系统。特别针对A10:2025（异常情况处理不当）和A03:2025（软件供应链缺失）设计了专项课程。
- **链接**：https://www.securecodewarrior.com/zh/article/owasp-top-10-2025-whats-new-and-how-secure-code-warrior-helps-you-stay-aligned

### 3.3 Authgear - A10:2025 异常情况处理不当新手指南
- **名称**：OWASP Top 10 2025：A10—异常情况处理不当（新手指南）
- **简介**：深入解析A10:2025的CWE映射、攻击场景及修复策略。提供代码示例（如Java、Python）展示如何避免fail-open和敏感信息泄露。
- **链接**：https://www.authgear.com/zh-hant/post/owasp-2025-mishandling-of-exceptional-conditions

### 3.4 GitLab - OWASP Top 10 2025 完整解读
- **名称**：OWASP Top 10 2025: What's changed and why it matters
- **简介**：从DevSecOps视角解读2025版变化，重点分析A03:2025（软件供应链缺失）与DevOps流程的整合，以及如何使用SBOM和依赖扫描工具进行编码实践。
- **链接**：https://about.gitlab.com/blog/2025-owasp-top-10-whats-changed-and-why-it-matters

### 3.5 Plexicus - OWASP Top 10 修复指南（2026版）
- **名称**：OWASP Top 10详解：每个风险及其修复方法（2026指南）
- **简介**：提供针对每个OWASP Top 10风险的代码级修复指南，包含Java、Python、JavaScript等语言的示例代码。强调从“检测”到“预防”的编码实践转变。
- **链接**：https://www.plexicus.ai/zh/glossary/owasp-top-10

## 4. 技术趋势

### 4.1 从“漏洞扫描”到“安全编码内建”
- 2025版强调风险应从编码阶段预防。趋势显示，静态应用安全测试（SAST）工具正在从单纯检测漏洞转向提供即时修复建议。例如，A03:2025要求开发者在编码时即集成SBOM生成，而非事后扫描。

### 4.2 异常处理成为安全编码新基线
- 随着A10:2025的独立，业界开始将异常处理视为安全编码的核心组成部分。趋势包括：使用结构化错误处理框架（如Java的Exception Handling Best Practices）、避免在异常中泄露堆栈跟踪、以及采用fail-safe（安全失败）设计模式。

### 4.3 供应链安全编码自动化
- A03:2025推动CI/CD管道中集成安全编码检查。趋势包括：自动依赖更新（如Dependabot）、软件物料清单（SBOM）的自动生成与验证、以及基于策略的容器镜像扫描。2025-2026年，预计将有更多工具支持“编码即策略”模式。

### 4.4 加密敏捷性与后量子准备
- A04:2025的扩展反映了加密技术面临的量子威胁。趋势要求开发者在编码时采用可配置的加密算法库（如Google Tink、AWS Encryption SDK），支持算法降级和密钥轮换，为后量子密码学（PQC）过渡做准备。

### 4.5 大型语言模型（LLM）安全编码辅助
- 2025版首次提及AI/ML相关风险（虽未独立成类），但安全编码实践正引入LLM辅助代码审查和漏洞修复。趋势显示，开发者需警惕LLM生成代码中的安全缺陷，并采用人工审核+自动化工具的双重验证机制。

## 5. 参考来源

1. Orca Security. *OWASP Top 10 2025: Key Changes & What They Mean*. https://orca.security/resources/blog/owasp-top-10-2025-key-changes
2. Secure Code Warrior. *OWASP 前10名：2025年—新增内容以及安全代码勇士如何帮助您*. https://www.securecodewarrior.com/zh/article/owasp-top-10-2025-whats-new-and-how-secure-code-warrior-helps-you-stay-aligned
3. Reddit. *OWASP Top 10:2025 已经发布！我们有新数据和新风险，但目标一致*. https://www.reddit.com/r/programming/comments/1ostz5x/the_owasp_top_102025_is_out_we_have_new_data_and?tl=zh-hans
4. LinkedIn (OWASP Foundation). *The OWASP Foundation Unveils The 2025 Top 10 List*. https://www.linkedin.com/pulse/owasp-foundation-unveils-2025-top-10-list-introducing-t2jce
5. OWASP Foundation. *OWASP Top 10:2025*. https://owasp.org/Top10/2025
6. Authgear. *OWASP Top 10 2025：A10—異常情況處理不當（新手指南）*. https://www.authgear.com/zh-hant/post/owasp-2025-mishandling-of-exceptional-conditions
7. F5. *优先扫描关键风险：OWASP Top 10 2025*. https://www.f5.com.cn/company/blog/scanning-for-what-matters-most-owasp-top-10
8. 叡揚資訊 (GSS). *GSS 資安電子報0241 期【OWASP Top 10 2025 的演變】*. https://www.gss.com.tw/en/security-epaper/4657-gss-241-owasp10-1
9. 台灣電腦網路危機處理中心 (TWCERT). *OWASP 2025年Web應用安全十大威脅揭曉，存取控制漏洞位居榜首*. https://www.twcert.org.tw/tw/cp-104-10548-03edd-1.html
10. GitLab. *OWASP Top 10 2025: What's changed and why it matters*. https://about.gitlab.com/blog/2025-owasp-top-10-whats-changed-and-why-it-matters
11. Plexicus. *OWASP Top 10详解：每个风险及其修复方法（2026指南）*. https://www.plexicus.ai/zh/glossary/owasp-top-10