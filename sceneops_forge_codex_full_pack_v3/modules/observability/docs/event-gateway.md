# 事件网关与重连

## 边界

`ObservabilityGateway` 是日志与进度的入口/查询投影，不是新的领域事件总线。领域模块提交 typed `StructuredLogEvent` 或 `ProgressEvent`；本模块执行字段 allowlist、脱敏、去重和排序，然后提供查询。

生产部署中，core event transport 负责跨进程传输和持久化。它应把已经符合本模块合同的记录送入同一个入口，不得另建模块专用 SDK 通道。

## 关联上下文

每条记录携带：

```json
{
  "project_id": "prj_...",
  "run_id": "run_...",
  "job_id": "job_...",
  "correlation_id": "corr_...",
  "causation_id": "cmd_or_evt_..."
}
```

Gateway 不生成、不修改这些 ID。Job 记录应同时提供 `run_id` 与 `job_id`。查询可按这些字段精确过滤。

## 至少一次投递

重复投递是预期行为：

1. 首次 `event_id` 分配内部序列；
2. 相同 ID 与相同完整 producer payload 再次提交时返回原记录；
3. 相同 ID 与不同 payload（即使差异会在脱敏后消失）也被拒绝为冲突；
4. consumer 仍应按事件 ID 幂等处理。

完整 payload 的比较使用进程内随机密钥 HMAC；网关不保留未脱敏 payload。去重记录随事件保留窗口一起裁剪，持久 transport 必须提供等价的耐久唯一性。

## 重连游标

客户端只持有服务端随机签发的客户端不透明游标，不解析、不构造内部状态。游标不是身份凭据，但会绑定项目；跨项目复用会被拒绝。重连请求必须携带 `project_id`，并只返回该项目在游标之后的记录和新的游标。

如果历史已裁剪，或不透明游标已从有界服务端 LRU 保留表中淘汰，API 返回 `EVENT_CURSOR_EXPIRED`；随机伪造或跨项目游标仍返回 invalid。客户端必须：

1. 重新查询当前领域投影或日志页面；
2. 清晰提示用户发生了历史窗口重置；
3. 从当前游标重新订阅。

禁止把过期游标当成空结果，因为这会静默遗漏失败事件。

## 组合步骤

1. 在 core transport 冻结后实现持久 `ObservabilityQueryPort`；
2. 把 `create_router` 注册到 `services/api` 的生成模块目录；
3. 从 Pydantic/OpenAPI 生成 TypeScript 客户端；
4. 在前端 transport 中将 SSE/WebSocket reconnect 映射为这里的不透明游标；
5. 运行进程重启、重复投递和游标裁剪 E2E。
