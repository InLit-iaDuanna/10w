# Design ChangeSet 审批

对现有 Bible 或 Feature Spec 的 assistant 修改必须先调用 propose 命令。ChangeSet 保存完整前值与建议值、baseVersionId、理由、预期结果、影响范围、风险、验证计划、回滚计划和审批要求。

approve 命令校验：模块启用、`design:approve` 权限、状态为 waiting-approval、当前版本仍等于 base version。通过后才追加新文档版本，并把 ChangeSet 标记为 applied。base 变化时返回 `BASE_VERSION_CONFLICT`，要求重新生成建议；不会偷偷 rebase 或覆盖。
