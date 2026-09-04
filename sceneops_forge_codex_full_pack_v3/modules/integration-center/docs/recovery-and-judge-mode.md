# 恢复与 Judge Mode

## Job 恢复序列

```text
timeout/failure
  -> load durable operation
  -> verify project/run/job/correlation context; preserve the new action causation ID
  -> lookup idempotency ledger
  -> reconcile when side effect may have started
  -> completed/running: do not duplicate
  -> not-found/failed: apply retry safety
  -> persist new attempt with prior recoverable state + side-effect unknown
  -> retry with new attempt ID OR resume with adapter token
  -> mark running + started only after dispatch acknowledgement
  -> preserve completed step IDs
```

每个动作在首次外部调用（包括预派发对账）之前，先把 action、idempotency key、目标 attempt、完整 action correlation context 和 `pending` 状态作为 recovery intent 写入 Job aggregate。Controller 返回后 intent 变为 `acknowledged`；异常窗口变为 `unknown`；下一动作必须先按不可变 `operation_id` 对账，并把确定结果逐条写入所有旧的 pending/acknowledged/unknown intent 后将其变为 `reconciled`。同 key 在确定未找到或已失败后安全重派时，intent 会进入新的 pending/acknowledged 阶段，但固定空间的 `last_reconciliation` 与饱和 `reconciliation_count` 会保留最近结论及已持久化确定结论的状态迁移累计次数；生产审计存储负责保存每次完整状态迁移。对账端口禁止按当前 recovery key 查找操作，因此 K2 不会把已被外部接受的 K1 误判为不存在。Cancel 同样遵守此规则，不能绕过对账直接重发。

Cancel 是请求，不是终态。Worker 或工具必须在后续事件中确认 cancelled；如果外部副作用状态不明，系统保持 pending reconciliation。

非幂等操作不能走 Retry。它只能通过具备 checkpoint 的 Resume、adapter compensation，或经过审批的专用恢复决定继续。任何会编辑生产项目的恢复动作仍必须由拥有该业务的模块创建 ChangeSet 并通过审批。

## 持久性要求

生产必须把 job state、历史 attempt ID、recovery intents 与 idempotency ledger 放在事务性持久存储中，并确保 `(integration_id, job_id, idempotency_key)` 唯一。Job aggregate 的 intent 写入/状态迁移与对应 ledger 结果应置于同一事务；已归档的 reconciled intent 应转移到审计存储，保持活跃 aggregate 在 256 条上限内。恢复动作的 causation ID 与原始操作 causation 分开保存。仓库内 memory 实现只用于 `mock` fixture；它不能跨进程提供保证。

## Judge fallback

Judge summary 不把 UI 可用性等同于工具健康：

- `live`: 当前、未过期的真实 probe；
- `cached`: 同项目、未过期的历史真实 run，必须有 `source_run_id`；
- `mock`: 固定 fixture，只演示功能和失败解释；
- `planned`: 尚未执行；
- `blocked`: 无法执行并提供原因。

工具断开时优先显示来源明确的 Cached 证据；如果另一个集成存在健康 Live probe，可继续提供短 Live step。无证据则明确 Blocked。

## Worker restart

当前模块只返回指导步骤，不执行重启。真实 restart 需要：

- allowlisted `worker-control` adapter command；
- 当前任务停止/对账；
- 权限与必要审批；
- correlation/causation IDs；
- progress/log/error mapping；
- restart 后新 health probe。
