# Integration Center

## 独立 Web 工作台（新增）

现在可通过 [integration-ops 启动说明](../../apps/labs/integration-ops/README.md) 独立打开 React 工作台：`pnpm --dir apps/labs/integration-ops dev`（从应用根运行，首次先安装依赖）。地址 `http://127.0.0.1:4320`。界面提供健康/能力、Worker、作业进度、项目/任务/correlation 筛选、日志与本地证据、诊断摘要。演示数据全部 Mock，固定时间明确显示。

新增公开 `create_demo_workbench`、`create_workbench_router`、`OperationsWorkbench` 与前端 `loadIntegrationOpsWorkbench`。网络类型从组合 API 的 OpenAPI 生成，TanStack Query 负责服务状态。原恢复、安全与脱敏机制保持不变；独立入口仅授权只读演示查询和诊断导出。

Integration Center 统一展示外部工具与 Worker 的实时探测结果、版本、能力、当前任务、队列、关联日志和恢复建议。它只依赖 vendor-neutral typed adapter，不导入 Blender、Unity、ComfyUI、Git 或存储 SDK。

## 用户与场景

- 制作人员在运行构建、渲染或资产任务前理解“为什么不可用”；
- 运维人员查看 Worker 心跳、任务、队列和 correlation ID；
- 用户安全地请求 timeout、cancel、retry 或 resume；
- Judge Mode 在工具断开时解释 Cached/Mock/Blocked fallback；
- 其他模块通过公共 Gateway 查询 health/capabilities，不接触 vendor 类型。

## 公共编辑器

### `integration.health`

显示：

- 七种 summary 状态：connected、disconnected、degraded、incompatible、busy、unauthorized、unknown；
- 独立的 connection、authorization、compatibility、availability、activity 事实；
- tool/adapter version、capability IDs 与 allowlisted command IDs；
- observed/expiry/last-seen 时间；
- 当前 Job、队列、关联日志与 Artifact ID；
- Live/Cached/Mock/Planned/Blocked 标签；
- 每个不可执行操作的具体原因与恢复命令。

`busy` 是活动状态，不等同于断线。summary 的确定性优先级是：

```text
expired -> unknown
disconnected -> incompatible -> unauthorized -> degraded -> busy -> connected -> unknown
```

只有 health probe 与 capability report 都处于各自新鲜窗口、均为 `live` 且 summary 为 connected/busy 时，才可设置 `live_actions_enabled=true`。Mock、Cached、过期或未来证据即使显示“已连接”也不能启用 Live 操作。

### `worker.monitor`

显示 Worker lifecycle、observed/expiry、新鲜度、最后心跳、版本、能力、当前任务、进度、队列、关联日志和恢复按钮。服务端按当前时钟重算 `is_current`；非幂等任务的 Retry 明确禁用；存在 adapter-issued resume token 时才允许 Resume；任何非 Live 或已过期 Worker 的 cancel/retry/resume 都禁用。

两个编辑器都提供 loading、empty、ready、failed、disconnected 和 permission-denied 状态，支持搜索及只序列化本地筛选/选中项。

模块保留可独立测试的 editor render model、懒加载注册和 typed client/command port；独立工作台已增加 React 宿主、TanStack Query 与生成网络类型。全局 Shell runtime 的挂载仍由 Shell 组整合。

## 公共命令

| 命令 | 权限 | 行为 |
|---|---|---|
| `integration.health.refresh` | `integration:read` | 通过 injected typed client 执行新探测 |
| `integration.open_logs` | `observability:read` | 生成统一 `workbench.open_editor` action |
| `integration.open_setup` | `integration:read` | 打开设置与恢复文档 |
| `job.cancel` | `job:operate` | 请求取消，但不声称外部副作用已停止 |
| `job.retry` | `job:operate` | 对账后安全重试 |
| `job.resume` | `job:operate` | 使用 adapter-issued checkpoint 恢复 |
| `worker.restart.guidance` | `job:read` | 只打开安全指导，不直接重启进程 |

Chat、按钮和菜单应注册这些相同定义。模块不直接调用 shell DOM 或 Dockview。

## 公共事件

- `integration.health.changed@1`
- `job.recovery.requested@1`

版本化 schema 位于 `contracts/events/`。`build_health_changed_event(...)` 与 `build_recovery_requested_event(...)` 生成符合根 event envelope 的 typed event，并保留 project/run/job/correlation/causation IDs。当前模块不自建事件总线；未来 composition root 通过 core transport 发布这些结果。

## Typed adapter 合同

Python `IntegrationAdapter` 只暴露：

```text
health_check(CorrelationContext) -> HealthProbe
capability_report(CorrelationContext) -> CapabilityReport
```

每次 health 查询都会真正调用当前 adapter probe。未注册 adapter 返回 `unknown` + `blocked`，而不是根据配置文件显示健康。工具版本必须由 adapter 规范化为 `major.minor.patch`；Gateway 根据声明的 version range 和 capability requirement 推导 compatibility。

详见 [Adapter 合同](docs/adapter-contract.md)。

## 熔断器

- 只统计 transient/infrastructure failure；
- unauthorized、incompatible 和 validation failure 不打开熔断器；
- 达到阈值后进入 open，并给出 retry time；
- cooldown 后只允许一个 half-open probe；
- 成功 probe 关闭熔断器；
- open 期间刷新操作带明确不可用原因。

## Timeout、Cancel、Retry、Resume

`RecoveryCoordinator` 需要注入三个接口：

- `RecoveryRepository`：Job/operation/attempt/side-effect/checkpoint 状态；
- `RecoveryLedger`：持久 `(integration_id, job_id, idempotency_key)` 账本；
- `JobControlPort`：allowlisted cancel、reconcile、retry、resume。

`reconcile_operation` 必须只按 Job 中不可变的 `operation_id` 查询整个逻辑操作，不能用当前 recovery idempotency key 作为查找条件。这样新 key 不能把旧 key 的未决派发误判为不存在；一次确定的 operation 结果会逐条写回每个旧 intent。若同 key 在确定未找到或已失败后安全重派，固定空间的 `last_reconciliation` 与饱和 `reconciliation_count` 会保留最近结论与已持久化结论的状态迁移计数。

关键不变量：

- logical operation ID 在 attempt 间保持不变；
- Retry/Resume 使用新的 attempt ID；
- 当前与历史 attempt ID 都不能复用；
- completed step IDs 传给 adapter，防止重复已完成副作用；
- side effect 为 started/unknown/completed 时先 reconcile；
- reconcile 显示原操作 completed/running 时不发起重复请求；
- non-idempotent Retry 被拒绝；
- Cached/Mock/Planned/Blocked Job 的恢复状态变更会被拒绝，不能触达 controller；
- Resume 必须有 adapter-issued token 且总是先 reconcile；
- Cancel 只进入 `cancel_requested`，不谎称 `cancelled`；
- project/run/job/correlation 必须匹配已记录操作；跨项目不匹配统一表现为未找到；每个恢复动作提供新的 causation ID，并在结果、事件及预派发 recovery intent 中原样保留，Repository 中原始操作 causation 不被改写；
- 同一 idempotency key 绑定其他 action/operation 时拒绝。

在任何外部 controller 调用前，Repository 先写入 recovery intent（action、key、attempt、action context、state）；派发前再写入新的 attempt 与 `side_effect_state=unknown`，但保留原来的可恢复 Job state。只有 controller 返回成功后才转成 `running/started` 与 `acknowledged`。如果进程在 cancel/retry/resume dispatch 窗口失败，intent 保持 `unknown`，下一动作必须先对账，不能把它当成从未执行。`JobControlPort` 同时必须在 adapter 侧按 idempotency key 去重。

仓库内 `InMemoryRecoveryRepository` 与 `InMemoryRecoveryLedger` 只用于确定性 Mock 测试。生产接入必须注入 durable 实现，才能跨进程重启保持语义。

## Judge Mode

`judge_summary(...)` 为每个集成返回明确 fallback：

- 新鲜 Live probe 可提供短 Live step；
- 当前工具不可用但同一项目存在仍在有效期内的历史真实运行时使用 `cached`，同时保留 `source_run_id`；
- 只有 fixture 时显示 `mock`，不作为真实执行证据；
- 没有任何可用证据时显示 `blocked`。

混合模式的总状态优先级为 Blocked > Mock > Cached > Live。界面文案说明工具为何不可用以及使用何种证据。

详见 [恢复与 Judge Mode](docs/recovery-and-judge-mode.md)。

## API

公共入口 `integration_center.create_router(service, recovery, require_permission, authorize_project)` 提供未来组合根可注册的 FastAPI 路由。`require_permission` 是必填粗粒度 core-auth dependency factory，`authorize_project` 必须逐请求校验项目成员资格，避免调用方通过自选 project ID 越权：

```text
GET  /api/v1/integration-center/integrations
GET  /api/v1/integration-center/integrations/{integration_id}
GET  /api/v1/integration-center/workers
GET  /api/v1/integration-center/workers/{worker_id}/restart-guidance
GET  /api/v1/integration-center/judge/health
POST /api/v1/integration-center/jobs/{job_id}/timeout
POST /api/v1/integration-center/jobs/{job_id}/cancel
POST /api/v1/integration-center/jobs/{job_id}/retry
POST /api/v1/integration-center/jobs/{job_id}/resume
```

Pydantic 模型是网络合同来源。当前 API 测试会生成 OpenAPI 并验证 health/recovery schema；生成 TypeScript client 属于任务 20/模块运行时集成，不在本模块手写网络 DTO。

## Fixtures

`contracts/examples/integration-health.mock.json` 提供：

- Blender connected；
- Unity busy；
- ComfyUI degraded；
- Git unauthorized；
- Artifact Store disconnected。

`contracts/examples/workers.mock.json` 提供 Blender、Unity、ComfyUI Worker。全部固定 ID/时间且明确为 `mock`。Unknown 与 incompatible 由到期和 capability/version mismatch 测试确定性生成。

## 执行状态

| 模式 | 当前实现 |
|---|---|
| Live | 本地 API 可启动；无 vendor adapter 或真实 Worker，外部功能不声明 Live |
| Cached | 合同与 Judge fallback 已实现；Blocked：没有真实历史 run/cache repository |
| Mock | Implemented：五类集成 fixture、Worker fixture、Gateway/recovery/API/editor 测试 |
| Planned | 全局 Shell 注册、持久 operation ledger、core event emission；独立工作台已具备 generated client 和 React mount |
| Blocked | 应用注册依赖缺失的 `core-kernel`、`module-runtime`、`services/api` 与 adapter modules |

## 开发与测试

后端：

```bash
cd modules/integration-center
PYTHONPATH=backend/src:../observability/backend/src python3 -m unittest discover -s backend/src/integration_center/tests -v
```

前端合同与 editor model：

```bash
cd modules/integration-center
pnpm --dir frontend test
```

测试覆盖七态、到期、版本/能力不匹配、Mock 禁止 Live 操作、fresh probe、熔断、timeout/cancel/retry/resume、对账/幂等、上下文 ID、API/OpenAPI、日志关联、Worker fixture 与 Judge fallback。

## Limitations

- 尚无根 core `ExecutionMode`/event transport 包；当前 Python 模块从 observability 的公共镜像使用根规格中的五值 enum。core 合同落地后应由 principal 统一替换并运行兼容测试。
- 本任务没有获得 principal 对 shared core gateway/event transport 文件的写入分配，因此未创建竞争性的 core transport。
- 没有真实 adapter、凭据或 Worker，所有可执行证据均为 `mock`；没有内容被宣称为 Live。
- 独立 React 工作台和生成客户端已实现；全局 Shell 集成与应用级 E2E 未完成。本轮仅运行启动及一条主路径烟测，其他测试 not run / pending approval。
- `IntegrationAdapter` 端口本身不启动线程或强行中断工具 SDK；生产 adapter 必须在自身网络/进程边界实现 deadline 与 cancellation，之后才能声明 Live。
