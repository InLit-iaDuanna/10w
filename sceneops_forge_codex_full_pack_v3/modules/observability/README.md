# Observability

Observability 为 SceneOps Forge 提供统一的结构化日志、任务进度、关联查询、断线重连投影和安全诊断包。它只处理可观察性数据，不判断 Blender、Unity、构建或其他业务是否成功，也不直接调用任何工具 SDK。

## 用户与场景

- 制作人员按项目、运行、任务或 correlation ID 定位失败链路；
- 集成与 Worker 编辑器显示关联日志和产物链接；
- 支持人员下载经过双重脱敏的诊断包；
- 前端事件连接断开后使用服务端签发、项目绑定的客户端不透明游标恢复，避免重复显示；
- Judge Mode 与其他模块可明确展示 `live`、`cached`、`mock`、`planned`、`blocked`。

## 公共能力

### 编辑器

`observability.logs` 是懒加载系统编辑器贡献，默认位于底部。它提供：

- loading、empty、ready、failed、disconnected、permission-denied 状态；
- 日志级别、来源模块、工具和 Worker；
- project/run/job/correlation/causation ID；
- allowlist 结构化字段和 Artifact ID 链接；
- 执行模式标签；
- 搜索与诊断包命令状态。

当前仓库尚无 React/Core UI 与 generated API client。模块已完成可测试的 editor render model、懒加载定义、序列化本地筛选状态和 typed client port；React 宿主绑定属于后续组合工作。

### 命令

| 命令 | 权限 | 行为 |
|---|---|---|
| `observability.logs.search` | `observability:read` | 通过 injected typed client 查询日志 |
| `observability.diagnostic.export` | `observability:export` | 在存在项目上下文时下载脱敏 ZIP |

组件不得自行 `fetch`。组合根用生成客户端实现 `ObservabilityClient`。

### 事件

- `observability.log.recorded@1`
- `job.progress.reported@1`

版本化 JSON Schema 位于 `contracts/events/`。所有记录携带项目、运行、任务、correlation 与 causation 上下文；生产者不能自行分配本模块的内部序列号。

### Python 公共入口

其他模块只从 `observability` 导入：

- `StructuredLogEvent`、`ProgressEvent`、`CorrelationContext`；
- `ObservabilityQueryPort`；
- `ObservabilityGateway`；
- `DiagnosticBundleService`；
- `Redactor` 与结构化错误类型。

`integration-center` 只使用 `ObservabilityQueryPort`，不导入本模块内部文件。

## API

公共入口 `observability.create_router(gateway, require_permission, access, ...)` 返回模块路由，供未来 `services/api` 组合。`require_permission` 是必填的粗粒度 core-auth dependency factory；`access` 还必须逐请求校验项目成员资格，并把写入者绑定到获准的 source module/tool 与 execution mode。模块不能以无鉴权默认值挂载：

| 方法与路径 | 用途 |
|---|---|
| `POST /api/v1/observability/logs` | 写入并在持久化前脱敏日志 |
| `POST /api/v1/observability/progress` | 写入进度事件 |
| `GET /api/v1/observability/events?project_id=...&cursor=...` | 从项目绑定的不透明游标恢复事件 |
| `POST /api/v1/observability/logs/search` | 结构化搜索 |
| `POST /api/v1/observability/diagnostics` | 下载 ZIP 诊断包 |

日志搜索的 `project_id` 必填，事件流与游标也始终绑定单一项目。重复 `event_id` 且完整 producer payload 完全相同时返回原记录；同一 ID 携带不同 payload（包括只改变秘密值）时返回 `EVENT_ID_CONFLICT`。网关只保留基于进程内随机密钥的 payload HMAC，不保存未脱敏 payload；这是为同时满足完整幂等比较与秘密不落库而设置的具体边界。游标已经被裁剪时返回 `EVENT_CURSOR_EXPIRED`，调用方必须重新查询当前投影，不能静默丢事件。

## 搜索字段

默认只允许以下结构化字段进入索引：

```text
artifact_id
attempt
code
duration_ms
integration_id
operation
queue_depth
status
```

未知字段会被拒绝，而不是形成不受控索引或绕过脱敏。消息文本仍可全文搜索。

## 诊断包

ZIP 固定包含：

```text
health.json
logs.jsonl
manifest.json
```

导出按 project ID 和可选 correlation ID 限定范围。调用方不能提交执行模式、生成时间或健康快照来伪造 provenance：时间由服务端 UTC clock 提供，模式由包内日志证据保守推导，无日志时为 `blocked`，健康数据只能来自 composition 注入的可信 provider。入口已脱敏的日志在导出前再次脱敏，超过 2,000 条时 manifest 明示 `logs_truncated=true`。ZIP 条目排序与时间元数据固定；测试可注入固定 clock 获得确定性字节。Artifact 的持久化、校验和与下载授权仍由未来 core-storage 负责。

## 数据所有权

本模块拥有日志/进度查询投影、游标语义和诊断包格式，不拥有业务实体、集成健康结论、Job 状态机或 Artifact 内容。当前 `ObservabilityGateway` 是线程安全的进程内投影，持久 event transport 必须由组合根注入或替换。

## 执行状态

| 模式 | 当前实现 |
|---|---|
| Live | Planned：尚无 core event transport、数据库或已启动 API 服务 |
| Cached | 合同已支持；Blocked：尚无真实历史运行与持久缓存仓库 |
| Mock | Implemented：固定时间、固定 ID 的日志 fixture、事件投影与诊断导出测试 |
| Planned | generated OpenAPI TypeScript client、SSE 适配、持久存储 |
| Blocked | 应用级注册依赖缺失的 `core-kernel`、`module-runtime`、`services/api` |

任何模块测试结果都只证明本地实现和 `mock` fixture，不证明外部工具 Live 执行。

## 开发与测试

后端：

```bash
cd modules/observability
PYTHONPATH=backend/src python3 -m unittest discover -s backend/src/observability/tests -v
```

前端合同与 editor model：

```bash
cd modules/observability
pnpm --dir frontend test
```

测试覆盖 manifest/public API、UTC 合同、重复事件、游标重连与过期、关联查询、字段 allowlist、秘密与路径脱敏、确定性诊断包、API 发布/搜索/下载，以及全部编辑器失败状态。

## 进一步文档

- [事件网关与重连](docs/event-gateway.md)
- [脱敏与诊断安全](docs/redaction-and-diagnostics.md)

## Limitations

- 根仓库尚未引导 core 合同、模块运行时、API composition root 或 generated client，因此未执行应用级注册、React mount 或 SSE E2E。
- 进程内投影不提供重启后的幂等、HMAC key 或游标耐久性；幂等记录和游标与保留窗口一起有界，生产接入必须使用持久 transport。
- 脱敏策略覆盖命名秘密、凭据、URL 与绝对路径，但无法识别完全无标记的任意随机秘密；producer 仍必须遵守“秘密不得进入日志”的入口契约，manifest 只声明已移除策略可识别的秘密。
- FastAPI composition root 仍需安装统一、已脱敏的 request-validation 与 unexpected-error handler；`APIRouter` 本身不能替换应用级默认错误序列化器。
- 当前“trace”能力是 project/run/job/correlation/causation 的可查询链路；专用 span/OTel exporter 与跨进程 trace backend 仍为 Planned，不能把本地事件投影描述成完整分布式追踪。
- 本模块不生成 Artifact 校验和，也不代替 core-storage 的下载授权与 provenance。
