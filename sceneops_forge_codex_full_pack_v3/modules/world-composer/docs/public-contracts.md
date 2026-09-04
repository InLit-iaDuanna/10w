# World Composer 公共合同

## 合同来源

本模块只拥有 world 领域载荷和磁盘/event payload schemas。核心 ID、`ExecutionMode`、`ActorRef`、`WorkbenchContext`、Typed Command/Event envelope、ChangeSet、Approval、Job、Artifact 与 Provenance 必须由 `core-contracts` 单一来源提供。当前源码中的 `WorldExecutionMode` 和 `WorldContextProjection` 明确是模块投影，正式集成时由生成类型替换，不建立第二套网络事实来源。

## 坐标

- scene 文档：meters、right-handed、Y-up、-Z-forward；
- viewer matrix：column-major，列向量；
- object anchor 同时保存 `sceneops_id`、local/world position、local/world normal；
- free point 的 local 值是 scene-root local，与 world 值相同，不伪造对象；
- point 使用完整齐次矩阵，normal 使用 `transpose(inverse(M3x3))` 并归一化；
- singular transform、zero normal、NaN/Infinity 均明确失败。

## Stable identity

对象名、node key、路径和数组索引仅用于定位/显示。rename 保留 `sceneops_id`；copy 必须由 core ID service 提供新 ID，同时保留 asset lineage。任何重复、缺失或重用 ID 都失败。

## WorldAnnotation v1

公共上下文包含 project/scene/exact version、author、UTC timestamp、object/scene spatial reference、local/world point 和 normal、camera、problem、intent、constraints、acceptance、typed evidence、versioned game state 与 mode。

九个持久化类型：

1. `object-pin`
2. `surface-pin`
3. `point`
4. `region-volume`
5. `path-trace`
6. `relation-link`
7. `state`
8. `sketch`
9. `voice-draft`

Voice 必须保持 draft。Surface 记录 topology/geometry version、triangle indices 和 barycentric；拓扑不一致时返回 stale。Path point 与 sketch stroke 各有稳定局部 ID，序列化不得只剩 raster screenshot。

## WorldMutationPlan

这是 ChangeSet 的 world-specific input，字段包括：base version、target module/integration/scene/objects、previous/proposed、rationale、expected result、impact scope、risk、validation plan、rollback plan、approval roles 和 dry-run requirement。它必须交给 `ChangeSetGateway`；模块不能自行推进核心审批状态。

Asset placement 的 source asset ID、asset version ID 和新 scene instance `sceneops_id` 必须不同且可追溯。base scene version 不一致返回 `STALE_SCENE_VERSION`，不自动 rebase。

## Recipe

`graybox-explicit-v1` 和 `procedural-grid-v1` 都要求 recipe ID/version、seed、constraints 与坐标声明。相同输入产生相同对象列表；所有 ID 均由 core 注入。编译只生成 planned mutation，不执行生产写入。

## Issue restoration

`WorldIssueContext` 固定 scene/version、target IDs、camera、path、evidence、game state、build/run/step 和 mode。恢复顺序为 exact scene → stable IDs → camera → path → evidence → follow context。版本不匹配整体 blocked；对象或 evidence 缺失可 partial；pinned context 不修改。

## Level gates

每项输出 scene/version、mode、明确 rule、`pass | fail | blocked`、稳定 issue IDs、offending `sceneops_id`、evidence IDs 和 reason。结果按 issue ID 排序。

- collider-required 对象必须有 enabled、有效且策略允许的 collider；
- declared spherical spawn volumes 不能相交；
- 对明确 agent profile，至少一个 spawn 到每个 navigation target 可达；
- 每条 required path 的连续 node pair 必须存在方向正确的 edge；
- local/world scale 按对象显式 policy 检查；
- 每个 required source/predicate/target relation 必须存在。

输入不可用或 scene version stale 时返回 blocked，不使用命名、距离或最近表面启发式补齐。

## Events

`contracts/events/` 只定义 v1 payload。core envelope 必须补充 event ID/version、UTC occurred-at、project、correlation/causation、actor 和 mode。消费者必须以 event ID 幂等处理。
