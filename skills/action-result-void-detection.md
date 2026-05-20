# Skill: action-result-void-detection

## 触发条件
当监控系统或日志分析工具检测到在 'periodic_check', 'user_message', 或 'reflect' 等关键动作触发后，其返回结果或日志记录为空时触发。

## 行为规则
### 1. 检测方法
- **日志完整性检查**: 扫描指定时间段内（例如：最近1小时）的日志，查找 `periodic_check`、`user_message`、`reflect` 等关键事件。检查这些事件后，是否存在对应的 `result`、`output` 或 `analysis` 等字段。
- **数据流追踪**: 如果日志不完整，追踪这些关键动作的处理函数，确认其是否正常执行并返回了数据。重点检查函数末端的 `return` 语句或日志记录语句 (`logger.info`, `print` 等)。
- **空值断言**: 在测试环境中，对上述动作的返回值进行断言，确保其不为 `None` 或空列表/字典。

### 2. 修复建议
- **强制日志记录**: 在所有关键动作（`periodic_check`, `user_message`, `reflect`）的处理函数末尾，强制添加日志记录语句，即使没有产出有效数据，也要记录一个明确的“无数据”状态（例如：`logger.info("periodic_check completed, result is empty")`）。
- **事件处理优化**: 审查 `user_message` 和 `reflect` 的事件处理流程。确保接收用户消息后，至少进行基础的情绪分析或关键词提取；确保反思机制至少输出一个“无新见解”的结论。
- **统一输出格式**: 为所有动作定义统一的输出结构（例如：`{"status": "success/failed/empty", "data": ...}`），以便后续模块或日志系统能明确知晓处理结果。

### 3. 相关案例
- **案例1**: 用户发送消息“你好”，系统日志中 `user_message` 事件后没有任何 `analysis` 记录，导致后续推荐模块无法工作。修复后，系统强制在收到消息后记录 `analysis: {"intent": "greeting", "entities": []}`。
- **案例2**: `periodic_check` 每小时执行一次，但连续多次日志显示该事件后无任何输出。修复后，在检查函数末尾添加 `logger.info(f"Periodic check finished. Status: {check_result_status}")`，即使检查结果为“无更新”，也进行了记录。

## 元数据
- 版本: 1
- 创建时间: 2026-05-21T02:07:05.730273
- 来源: 自动生成
