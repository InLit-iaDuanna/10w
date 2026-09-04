# Production Planner Domain and State

## 领域模型

```text
FeatureSpecReference
  -> FeatureSpecProvider
  -> FeaturePlanningSnapshot
  -> ProductionPlan
       |- ProductionTask
       |    |- Assignment
       |    |- TaskInput / TaskOutput
       |    |- AcceptanceLink / AcceptanceEvidence
       |    |- Estimate[predicted|measured]
       |    |- Risk / TaskBlocker
       |    `- external comment, approval, deliverable references
       |- TaskDependency
       |- Milestone
       `- structural blockers
```

`FeaturePlanningSnapshot` 是 planner 端口的最小读取投影，不是 design-room 的 Feature Spec 源模型。真实 provider 必须从 design-room 公开 API 适配，不得读取其 repository 或内部文件。

## 任务状态机

```text
draft -> ready -> in_progress -> waiting_approval -> completed
  |        |          |                 |
  +------> blocked <---+-----------------+
  |        |
  `------> cancelled
```

补充规则：

- `blocked -> ready` 只在全部 blocker 带外部 resolution ref 解决后使用；
- `waiting_approval -> in_progress` 用于评审退回继续修改；
- `completed` 与 `cancelled` 为终态；
- 未确认计划只能进入 blocked/cancelled，不得开始生产；
- 上游任务未完成时，下游不能进入 ready、in_progress、waiting_approval 或 completed；
- completed 要求所有验收关联都有通过证据，并满足 task approval requirement。
- in-progress、waiting-approval、completed 和 cancelled 任务不能原地改写标题、描述、assignment 或计划结构；需要新的 Feature/计划修订。

## 计划确认

Planner 不实现 Approval 系统。`apply_plan_approval(plan_id, approval_ref_id)` 和 task completion 都先调用注入的 `ApprovalProvider`，只有 provider 返回 scope 与 scope ID 匹配的 verified record 才接受。模块保存外部引用，并确认任务与 assignment 建议。计划后续被编辑时会移除该引用并回到 `draft_unconfirmed`。

AI 发起的 `production.plan.create` 必须包含外部 `change_set_id`。Planner 只保存引用，不解释或修改 ChangeSet 内容。

命令 actor、AI 标志、mode、时间、correlation、causation/command 与 ChangeSet 不来自网络 body，而来自注入的 trusted `PlannerExecutionContext`。当前只接受 deterministic mock context；live/cached 必须等待 core-kernel adapter。

## 版本与幂等

计划 ID 由 Feature stable ID 与 Feature revision 决定。同一 revision 的 create 使用 create-if-absent：若计划已经存在，返回 `created=false` 和原计划，不重放 drafted event，不覆盖人工编辑、审批或证据。

每次领域更新递增 `plan_version`，repository 用 expected version 做 compare-and-swap。并发旧写入返回 `CONCURRENT_PLAN_WRITE`。Feature 内容变化必须先递增 Feature revision，再生成新的 plan ID 并运行影响分析。

## DAG 校验

结构性阻断包括：

- dependency 引用不存在的 predecessor/successor；
- predecessor 没有声明要求的 output；
- successor 没有与 dependency 对应的 task-output input；
- dependency cycle；
- milestone 引用不存在的 task；
- milestone 标记 ready/completed，但 required tasks 未完成。

有结构性阻断时计划状态为 `blocked`，关键路径不返回误导性结果。

运行时 blocker 由 task 拥有，包含 typed code、message、task IDs、resolved 标志与外部 resolution ref。Graph view 会把未解决 blocker 合并到节点、阻断列表和里程碑准备度。没有 blocker 不能进入 blocked，未解决时不能恢复 ready。

## 关键路径

关键路径使用 DAG 上最长累计工时。每个任务优先使用最新 `measured` Estimate；没有真实测量时使用 `predicted` Estimate。Graph view 同时返回每个节点的 estimate kind 和整条路径的 basis，不把预测值包装成实测值。

## 实测估算

`record_measured_estimate` 不接受 caller 提交的小时数、mode 或时间。它用 task/run stable IDs 查询注入的 `RunEvidenceProvider`，从 verified start/completion timestamp 推导工时。Provider 只可返回：

- `live` 的实际 run；
- 保留先前真实 run provenance 的 `cached` run。

`mock`、`planned` 与 `blocked` 不能成为 measured 数据；cached timing 必须带 originating live run ID。Provider 不可用时更新状态是 Blocked。新测量会追加到 estimates，绝不覆盖 predicted 或先前测量。

## 验收证据

证据必须同时引用 task ID、task 已关联的 criterion ID、声明的 evidence type、artifact ID、执行模式和 UTC 时间。每个 `expected_evidence` 类型都要分别满足；一份笼统证据不能代替同一标准要求的多种证据。live 计划只接受 live/cached 通过证据；mock 计划只接受 mock 证据。证据记录不归 planner 所有，planner 只保存其关联投影。

## Feature 修订影响

影响分析比较相同 feature ID 的两个 planner snapshots：

1. 找出新增、删除或内容变化的 acceptance criteria；
2. 标记直接引用这些 criteria 的任务；
3. 沿 dependency graph 向下游扩散；
4. 若 feature title/summary 变化，从 design task 开始扩散；
5. 返回 affected task IDs 与逐任务原因，不直接改写或重置既有工作。
