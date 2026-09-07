# Harness Kernel V5

该包提供现有工作台的持久化流水线内核与 Pydantic 公开契约。它不启动服务，不调用模型，不运行 Blender/Unity，不加载任意脚本，也不会把计划转换成假执行结果。

公开入口为 `sceneops_harness`。所有网络模型使用 snake_case，`PipelineDefinition.schema_version=5`，事件 `schema_version=1`。基础 `ExecutionMode` 与 `ChangeSet` 复用 `sceneops_core_contracts`。API 层应从这些 Pydantic 模型生成 OpenAPI/前端类型。

## 注册与组合

`CapabilityRegistry.register(definition, handler=None, *, input_model=None, output_model=None, rollback_handler=None)` 注册静态白名单。可执行 handler 必须有 Pydantic 输入/输出模型，模型生成的 JSON Schema 与显式声明必须一致。handler 不存在时只能声明 planned/blocked/cached 等不可执行能力；内核不提供缓存重放。

handler 接口为 `async (CapabilityInvocation, CancellationToken) -> CapabilityResult`。补偿接口为 `async (CapabilityInvocation, CapabilityResult, CancellationToken) -> CapabilityResult`，第二个参数是前向执行结果。可执行能力必须明确声明 live 或 mock；返回模式必须匹配注册模式。

`CapabilityInvocation` 包含 project/run/step/step_run ID、稳定的本次 invocation ID、attempt、已校验 inputs、直接依赖的 `dependency_outputs`、当前 authority、剩余 budget、完整 ChangeSet、snapshot_ref，以及 agent_task/model_routing。ID 不是文件路径，内核不进行路径解析。

能力提供者负责真实工具执行、允许命令、路径隔离、source version 与 snapshot 有效性检查、工具取消清理及证据真实性。模型输出不能直接作为代码或任意 adapter 命令执行。注册 `live` 必须有当前环境真实执行的依据；声明本身不证明 Blender/Unity conformance 已通过。

`ConnectorRegistry.register(ConnectorDefinition(...))` 更新连接状态；`CapabilityRegistry(connectors)` 使用该目录。调用前再次检查连接可用性。每个 required integration 使用 SQLite 独占锁，多个本地 API worker/项目不能同时使用同一连接器。

## Runtime API

构造 `HarnessRuntime(database_path, registry)`，database_path 可与现有工作台 SQLite 相同；仅创建自己的 `harness_runs`、`harness_events`、`harness_resource_locks` 表，不跨模块查询。数据库必须是文件，不能使用 `:memory:`。

| 方法 | 行为 |
| --- | --- |
| `validate(definition, authority)` | 返回 ValidationReport，不执行能力 |
| `submit(definition, authority, request_id)` | 持久化 queued 或 blocked 计划；相同项目/request_id 的相同提交返回原 run，不重放执行 |
| `await start(project_id, run_id, authority)` | 仅接受 queued/awaiting_approval；重新校验后逐步执行或暂停 |
| `get(project_id, run_id)` / `list(project_id, limit=50)` | 项目隔离读取；列表上限 200 |
| `events(project_id, run_id, after=0, limit=200)` | 按单调 sequence 读取持久事件；上限 1000 |
| `approve(project_id, run_id, step_id, authority, decision='approved', action='execute', inspection_confirmed=False)` | 记录明确审批；decision 可为 rejected，action 可为 rollback；不自动执行。补偿结果不确定时，检查外部实际状态后才能以 inspection_confirmed 重新批准 |
| `cancel(project_id, run_id, authority)` | 持久化取消请求；正在执行时等待 handler 清理 |
| `retry(project_id, run_id, authority)` | 校验重试次数/权限，保留成功步骤及所有尝试，清除未成功步骤的执行审批，重新 queued；不自动 start |
| `await rollback(project_id, run_id, authority)` | 仅调用有明确批准、rollback_ref 和 compensation handler 的已执行副作用，按实际执行顺序逆序补偿 |
| `recover_interrupted(project_id)` | 检查已死亡的本地 owner PID，将未完成运行明确 blocked；不自动续跑 |

Authority 必须由服务端从当前项目与已认证用户构造，不能接受模型/浏览器自报权限。默认 permissions/allowed_capabilities 为空。所有 API 读写必须先验证用户有权访问给定 project_id；内核的 project_id 参数负责数据分区，本身不是身份认证。start/retry 在调用时接收新 authority，逐步再次检查该 authority 和 registry；长运行中的外部权限撤回由宿主取消作业处理。

执行流程为 queued → running → completed/failed/blocked/cancelled，或 running → awaiting_approval → running。成功 step 是 succeeded，成功 run 是 completed。审批步骤单独成功不算生产任务已完成。未实现的状态枚举保留契约语义，并不表示其执行器已实现。

## 计划、审批和证据

当前实现 tool、agent、evaluator 和显式 approval。依赖按 DAG 拓扑排序顺序执行。stage 用于分组；跨阶段先后关系必须用 depends_on 明确表示。fan_out/fan_in/sub_pipeline/retry/rollback 节点类型及 named policies 明确报告 unsupported，不静默跳过。重试、补偿通过上述运行方法执行。

Condition 仅支持当前输入/输出顶层字段的 equals/exists；前置条件只能读取 inputs。输入/输出模式、证据类型/引用与声明的验收结果均进行检查；校验失败会保留 handler 已返回的结果，以便观察和处理实际副作用。

mutate/build 能力要求 typed ChangeSet 和 dry-run 支持，medium/high/critical 要求 snapshot_ref。实际 mutate/build 和 cross_system 调用暂停审批；dry-run 不执行前向副作用。审批需要 human authority 的 `harness:approve`，并同时满足 ChangeSet 的权限/人数要求。每个审批人只计一次。补偿要求单独批准，不把前向审批当作回滚授权。

重试是人工明确操作，不进行自动无限重试。次数受 run budget 与 capability retry policy 的较小上限约束。副作用重试还要求提供者明确声明 `side_effect_retry_safe`，否则要求检查工具状态。所有 attempt 及其错误、真实返回结果均保留。补偿在调用前持久化 rollback_state=running、消耗本次批准并记录 rollback_attempts；失败或重启标记 uncertain，必须检查外部实际状态并重新批准，不能凭旧批准重复补偿。没有 rollback handler 时不会假报 rolled_back。多人审批 ChangeSet 的补偿明确报 MULTI_APPROVER_ROLLBACK_UNSUPPORTED，不能降为单人批准。

事件与每次状态写入使用同一 SQLite 事务。执行前持久化 invocation；执行后持久化结果/检查点。事件记录本地观测到的事实，不等于外部动作成功的证据。进程在外部工具成功与数据库写入之间崩溃时，重启只能报告 interrupted，需要检查外部实际状态。

## 预算与真实状态

max_steps/max_attempts/执行时间有内核边界；输入的 agent budget 进一步收紧单次调用预算。已知 token/cost 报告超过预算会停止后续步骤。能力估计用于调用前预算检查，handler 收到剩余预算并负责提供者侧约束。

`CapabilityResult.tokens`/`cost_usd` 缺失时为 null，不伪造 0。`PipelineRun.tokens_used`/`cost_usd` 仅累计已知值，`budget_accounting_complete=false` 表示不是完整账单。CapabilityDefinition.metered 默认 true：开始调用前持久化用量未知，只有返回完整 usage 才恢复，因此失败、超时、取消、重启不能按 0 花费重试。确定性的免费本地 handler 应显式声明 metered=false 并返回 0；不能用 estimated_cost=0 推断免费。

RuntimeBudget.usage_policy 默认 `require_reported`：已有用量未知时停止后续计费调用。只有用户明确选择 `bounded_calls` 后，才允许未知用量下继续；宿主必须从明确用户预算设置构造该策略，不能让模型自行放开。此模式仅限制调用次数、步骤、尝试和执行时间，无法验证真实 token/货币硬上限，`budget_accounting_complete` 始终保留 false。已知 usage 仍受预算检查。

两种策略都有 `max_metered_calls`，默认 4，上限 32，0 禁止计费调用。每个计费 attempt（含补偿）开始前事务递增 `PipelineRun.metered_calls_used`，失败、取消和中断不退还次数。`CapabilityInvocation.budget.max_metered_calls` 是预留本次前可用额度，包含当前调用，最后一次为 1；不会把初始总预算重复交给后续 handler。AgentTask 的更小次数预算也适用。调用预算只覆盖 run 内已注册的计费 attempts，编译计划等 run 外请求必须由宿主单独披露及约束。

混合 live/mock run 总模式为 mock；每个 step 和 attempt 始终保留自身模式。缓存和规划条目不会自动执行 mock。注册 handler 返回不匹配模式、缺证据或无验收通过记录时停止执行。

## 测试与维护

`fixtures/mock-inspection-pipeline.json` 是显式 Mock 计划，没有启动副作用。`tests/test_runtime.py` 与 `tests/test_call_budgets.py` 维护主路径、失败、权限/项目隔离、审批、重试、取消、持久化、unknown usage、显式调用次数策略与计划不可用案例。此次实现期间这些测试均 **not run**；没有启动测试、服务、模型、demo、Blender/Unity 或构建。执行授权与最小烟测由组合根负责。

## Limitations

这是本地顺序 DAG 内核，尚无分布式执行、嵌套流水线、并行 fan-out、自动恢复改图、缓存重放和真实 Blender/Unity conformance。Pydantic 公开模型包含这些后续层需要的 Planning/Agent/Observation/Recovery/Distillation 数据，不等于对应生产能力已完成。

处理器必须遵守 async 取消并清理自己的子进程；Python 内核无法强制终止拒绝响应取消的外部 SDK。锁与重启检测使用本机 PID，不能用于多主机共享 SQLite；PID 复用可能保守地保留 blocked/busy，不能误称恢复成功。一次中断扫描最多检查该项目最近 200 个运行。

货币预算依赖提供者报告及其限制接口，不是支付系统硬限额。补偿当前只支持本来就允许单人审批的 ChangeSet，多人要求明确拒绝；应扩展补偿审批后再接入这类真实写入。
