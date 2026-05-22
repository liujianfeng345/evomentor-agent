# Skill: empty-action-output-log

## 触发条件
在 periodic_check 或 user_message 等动作执行后，结果日志为空或缺失有效数据。

## 行为规则
1. 检测方法：检查动作执行后的日志记录，若返回值为空、null 或仅包含空白字符，则触发此 Skill。
2. 修复建议：检查动作实现逻辑，确保在无数据时记录明确原因（如 `no_new_data`、`action_not_triggered`），并优化日志收集流程避免遗漏。
3. 相关案例：所有 periodic_check 和 user_message 的结果均为空，可能是日志记录不完整或动作未产出有效数据。

## 元数据
- 版本: 1
- 创建时间: 2026-05-22T14:20:31.488609
- 来源: 自动生成
