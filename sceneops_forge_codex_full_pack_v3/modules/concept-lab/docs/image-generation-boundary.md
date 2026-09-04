# 图像生成 adapter 边界

## Typed adapter

`ConceptGenerationAdapter` 只暴露：

1. `health_check()`：可用性、adapter ID、真实 execution mode 和原因；
2. `capabilities()`：支持视图、turn-around、模型列表；
3. `dry_run(request)`：返回视图、模型、mode、警告与审批要求；
4. `execute(request)`：返回 mode 一致的 `GenerationOutput`；
5. `cancel(run_id)`：取消支持异步运行的 adapter；同步 fixture 会明确返回 false。

供应商 SDK、凭据、重试、超时和结构化日志属于未来 concept-specific integration adapter。前端不得调用 SDK。能力报告包含 timeout、retry limit 和取消支持；服务会在运行前验证 adapter、mode、model、视图和 turn-around 能力，并在 execute 前执行 dry-run。缺失项产生可见的 `blocked` run，而不是伪造结果。

## 状态语义

生成 job 状态：

```text
queued -> running -> succeeded
   |          |----> failed
   |----------> blocked
   |----------> cancelled
```

终态不可再次转移。失败与 blocked 都保留 reason；成功保留 variant ID。`planned` 和 `blocked` execution mode 不会执行 adapter。

## Fixture 语义

Mock fixture 是合成的确定性数据。Cached fixture 是合同回放数据，用于验证 cached 标签、provenance 和许可提示；它不是当前主机 live 执行的证据。生产 cached adapter 必须只返回来自既有真实运行且仍有完整 provenance 的记录。

## Live 集成步骤

1. 在 concept-specific integration 目录实现 adapter，不在模块 UI 引入供应商 SDK。
2. 健康检查只在真实可调用时返回 `available=true` 和 `mode=live`。
3. 把 provider/model/prompt/negative prompt/seed/workflow version 写入每个 artifact provenance。
4. 将图片先写 artifact-store，再返回稳定 artifact URI 和由 artifact-store 计算的 SHA-256。
5. 注入 `ConceptLabService(adapters=[...])`，运行 adapter 合同测试和一次明确标记的 live smoke test。
