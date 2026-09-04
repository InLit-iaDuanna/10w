# Integration Adapter 合同

## 目的

功能模块需要健康与能力信息，但不能导入 vendor SDK。`IntegrationAdapter` 是最小公共端口；Blender、Unity、ComfyUI、Git 和 Artifact Store 各自在自己的 adapter 模块实现它。

## Probe 规则

`health_check` 必须在当前请求中实际观察工具。静态 enabled flag、上一次缓存或配置文件存在不能产生 `live connected`。

`HealthProbe` 包含正交事实：

- connection；
- authorization；
- availability；
- activity；
- observed/expiry/last-seen；
- current job 与 queue；
- execution evidence。

`CapabilityReport` 包含规范化 tool/adapter version、capability IDs、allowlisted command IDs、约束和 execution evidence。能力证据有独立 freshness TTL；过期或未来报告不能启用 Live action。禁止返回 vendor SDK object。

`WorkerSnapshot` 同样必须提供 observed/expiry 窗口。Integration Center 使用服务端当前 UTC 时钟重算 `is_current`，不能信任 adapter 的静态 Live 标记；非 Live 或已过期快照不能开放 Job control。

## 错误映射

Adapter 抛出 `AdapterError(code, safe_message, state, transient)`。`safe_message` 必须已经适合用户显示且不得包含秘密或本地绝对路径。

只有网络不可达、进程无响应、临时过载等 transient 错误计入 circuit。授权、兼容性、输入 validation、取消和审批错误不计入。

未知异常会映射为通用安全消息并按永久 contract/programming failure 处理，不计入 transient circuit；原始异常只可通过 observability 的脱敏入口记录。Gateway 会再次脱敏 adapter 的显示名、任务标题和 safe reason，不能只依赖 adapter 自我声明安全。

## 版本与能力

Adapter 把 vendor 版本规范化成 `major.minor.patch`。Gateway 只执行通用 range/capability 比较，不包含 vendor-specific 兼容逻辑。需要 vendor 解释的规则由 adapter 生成规范化 capability/constraint。

## 生产接线

1. adapter 模块声明自己实现 `IntegrationAdapter`；
2. composition root 读取模块 catalog 并显式注册实例；
3. adapter 健康调用使用 timeout 与 cancellation；
4. safe error/progress/log 进入唯一 observability transport；
5. contract tests 验证 identity、模式、时间、能力与错误映射；
6. Live smoke 成功前 Integration Center 仍显示 Planned/Blocked。

恢复 adapter 的 `reconcile_operation` 必须按不可变 `operation_id` 查询逻辑操作的当前/历史状态，并覆盖其所有 attempts；recovery idempotency key 只用于 cancel/retry/resume 的写请求去重，不得作为对账查询主键。
