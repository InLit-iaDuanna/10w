# Concept Lab 公共合同

## ConceptSpec

`ConceptSpec` 是版本化创作意图。尺寸统一为米，平台预算明确目标平台、三角面、纹理尺寸和材质槽上限。Project Bible、Feature、Task 只保存稳定 ID，不复制其他模块的数据。

AI 或用户提出的字段修改先形成 `ConceptChangeSet`。ChangeSet 保存 base version、前后值、理由、预期、影响、风险、验证与回滚计划；批准并应用后才生成新 ConceptSpec 版本。冲突 base version 会被拒绝。

图像生成 adapter 实现者可从 backend 公共入口导入 `ConceptGenerationAdapter`、`GenerationRequest`、`GenerationPlan`、`GenerationOutput`、`GenerationCapabilities` 和 `AdapterHealth`，不需要访问内部文件。

## Reference 与 provenance

每个参考图保存 source、license、permission status 和 artifact provenance。AI 输出额外保存 provider、model、workflow version、完整 prompt、negative prompt、seed 和参数。模块验证调用方提供的 SHA-256 字段，但不在 Concept Lab 重复实现 artifact-store 的文件摘要职责。

## 风格检查

检查输入是一组针对 Style Bible 声明项的证据：观察、证据 reference ID、verdict、confidence 与理由。聚合结果包含：

- `assessment`：consistent / needs_review / inconsistent；
- `confidence`：提交证据置信度的平均值；
- `evidence_coverage`：已评估声明项比例；
- `unevaluated_criteria`；
- 永远为 true 的 `is_subjective`。

该结果是决策证据，不是客观艺术结论。

## AssetSpecDraft v1

只有已批准且通过许可/必需视图 gate 的 variant 才能编译。草稿保留 ConceptSpec 版本、variant、approval decision、reference ID 和执行模式。其 `status` 固定为 `draft`，不会触发 Blender、发布或 AssetVersion 创建。

Prompt 07 的 Asset Factory 是最终 `AssetSpec` 合同所有者。集成时应显式映射 `asset-spec-draft.v1.schema.json`，不能导入 Concept Lab 内部类。

## API 错误

错误响应包含 `code`、`message`、`details`、`request_id`、`retryable` 和 `suggested_actions`。前端依据 code 与结构字段显示失败，不解析英文 message。
