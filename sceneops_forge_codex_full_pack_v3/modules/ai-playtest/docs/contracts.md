# AI Playtest 公共合同

## 核心实体

| 实体 | 关键语义 |
|---|---|
| `TestCase` | 版本、项目/场景、代理模式与 seed、目标、动作/时限/破坏性边界、故障阈值、回归指标 |
| `Observation` | UTC 时间、遥测序号、构建、场景、角色 pose、相机/截图、游戏状态、目标、可用动作、错误、性能采样 |
| `AvailableAction` | allowlisted kind、参数、目标 `sceneops_id`、注册动作 ID、目标相关性、破坏性与反馈预期 |
| `PlaytestStep` | 动作前 `observation`、动作后 `post_observation`、精确匹配的已公布动作、结果、进度、信号和证据 |
| `EvidenceBundle` | run/session、执行模式、构建/场景、步骤或初始检查点、相机、轨迹、artifact 与结构化日志 ID |
| `Issue` / `Backpin` | 可复现故障、恢复上下文、同构建源候选、置信度、歧义/未解析/人工确认/拒绝状态 |
| `PlaytestRun` | 追加式 run 身份、终态证据、adapter/行为/测量 recipe provenance、步骤、Issue、日志和测量值 |
| `RegressionComparison` | 精确配置校验、声明的指标方向/容差、问题变化和 AI 限制标签 |

Pydantic 是网络合同来源。TestCase 与 fixture 的 on-disk JSON Schema 位于 `contracts/manifests/`，事件 Schema 位于 `contracts/events/`。

## API

由 `create_router(service)` 提供：

- `POST /api/v1/playtests/runs`
- `POST /api/v1/playtests/runs/{run_id}/cancel`
- `POST /api/v1/playtests/regressions`
- `GET /api/v1/playtests/issues/{issue_id}/restore`
- `POST /api/v1/playtests/issues/{issue_id}/backpin-reviews`
- `POST /api/v1/playtests/issues/{issue_id}/change-proposals`

路由只验证并委派给 `AIPlaytestService`。回钉审核从可信的 `request.state.actor_id` 读取身份，正文只接受 `decision`。跨模块组合根负责注入 repository、adapter、认证、权限、事件传输与生成的 TypeScript client。模块处理的错误使用顶层 `ErrorBody`；FastAPI 请求校验错误仍需组合根安装统一 handler。

`run_id` 最长 96 字符，给 signal、evidence、issue、backpin、artifact 与 log 的派生稳定 ID 预留空间；run、cancel、regression、事件和前端命令使用同一限制。`RunFailure.suggested_actions` 只引用已注册的模块命令 ID。

## Run state

```text
queued -> running -> succeeded
                  -> failed
                  -> cancelled
                  -> blocked
```

终态必须带 `finished_at`；失败必须带 typed `RunFailure`；blocked 必须带原因；成功必须完成 TestCase 的全部目标且不得包含 critical signal。`comparison_eligible` 只在完整结束的 gameplay success/failure 上为真；取消、阻塞和 adapter/telemetry 中断明确为假。失败运行保留已经完成的 steps、初始/终态 evidence 和可取得的 adapter logs。相同 run ID 与相同 TestCase/build/mode/replay 幂等返回；冲突身份返回 typed 409。构建、场景、run/session、执行模式和遥测合同在边界逐项校验。

## 回归判定

baseline 与 candidate 必须均为 comparison-eligible，并拥有逐字段相同的 TestCase、replay action IDs、adapter provenance、runner/detector/policy/workflow 版本和实际测量 recipe 快照。构建 ID 可以不同。每个指标的 `maximize` / `minimize` 与 tolerance 由 TestCase 声明；缺失指标产生 `incomparable`，同时改善与退化产生 `mixed`。

Comparison 身份同样是追加式：相同 `comparison_id` 与相同 baseline/candidate 重投递会返回原结果（包括原 `compared_at`）；同 ID 换输入会返回 identity conflict，不会覆盖审计记录。

## 身份与审核不变量

- 每个 step 与 evidence 必须属于当前 run/build/scene；相邻 step 复用上一动作的 post observation。
- artifact 显式记录并校验当前 run 的 source project/version、相关 `sceneops_id`、producing module、tool/workflow version、creator、mode、时间与审批状态；可比较运行中的 evidence 只能引用该运行实际收集的 adapter log IDs。
- Backpin 只使用 evidence 同构建候选；SourceCandidate 的 `source_record_uri` 片段必须与 `source_record_id` 一致，并可在版本化 source catalog 中解析。`evidence_artifact_ids` 与故障 signal 的 artifact 引用使用同一命名和身份空间。`resolved` 仍只是候选；人工确认后才可创建 `changeset.propose`。
- 人工审核不可被第二次覆盖；拒绝状态保留原证据，仍可恢复现场。
- 恢复命令保留 `run_id`、`build_id` 和 execution mode；Mock/Cached 现场要求宿主确认后才能切换上下文。
