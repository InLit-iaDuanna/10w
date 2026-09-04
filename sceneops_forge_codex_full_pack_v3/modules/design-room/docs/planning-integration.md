# Design Room 到 Production Planner 的合同

`design.feature_spec.marked_ready@1` 是唯一的排期交接事实。payload 提供 Feature Spec/version 稳定 ID、依赖 ID、验收标准 ID和所需交付物，不包含任务、负责人、工期或里程碑。

Planner 应按 event envelope 的 `eventId` 幂等消费，并通过公开 API/稳定 ID获取完整版本。不得导入 Design Room repository 或 editor 内部实现。

准备度规则：

1. Project Intake 的目标平台和根目录已 confirmed。
2. Feature Spec 有目标、输入、输出、至少一个验收标准和测试需求。
3. 所有 acceptance criterion 均包含 Given/When/Then。
4. AI assumptions 已由用户确认或拒绝。

未通过时命令返回结构化 `DESIGN_NOT_ACTIONABLE`，不发 event。
