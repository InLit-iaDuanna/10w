# AI Playtest 集成说明

## Runtime adapter

运行时实现 `ai_playtest.ports.PlaytestRunnerAdapter`，不得把 Unity SDK 类型泄漏给模块。必须提供健康检查、能力报告、dry-run、带 run ID 的 reset、观察、可用动作、动作执行、游戏状态、目标进度、检查点/步骤证据捕获、遥测恢复、取消、测量和结构化日志。

Live 组合层在创建 `AIPlaytestService` 时注入 adapter 与 repository。模块不会自行发现进程、连接端口或执行任意脚本。

每次观察的 `build_id`、`scene_id` 和严格递增的 `telemetry_sequence` 都会校验。序号由 runtime adapter 的读取通道产生，deterministic fixture 不接受作者手写的序号。actions、game-state 和 goal-progress getter 必须来自同一个 Observation 快照；任一矛盾都会成为 execution-truth 错误。动作后的 post observation 直接成为下一动作的 pre observation，不会因重复读取同一帧制造假丢包。真实缺口只允许 adapter 恢复到精确下一序号，恢复事实始终记录为 `telemetry_loss` 信号。单动作 timeout 会被 `min(action_timeout_ms, remaining_run_duration_ms)` 夹住；adapter 必须遵守 timeout 与协作取消合同。

能力报告必须为 TestCase 的每个回归指标提供 `MeasurementRecipeProvenance`。运行只保存实际声明指标的 recipe 快照；同名指标若实现、版本或参数不同，不能声称 exact comparison。测量只基于已执行动作和已访问观察；未采到的值省略，由回归比较标为 `incomparable`。

## Unity extension point（Planned / Blocked）

当前规范包缺少 `engine-unity` 实现。未来的 Unity 公共 adapter 应将：

- `SceneOpsIdentity.sceneops_id` 映射为观察和动作 target；
- runtime action registry 映射为 `registered` action；
- Game View 截图/相机、角色 pose、NavMesh/collider、quest/game state 映射为 Observation；
- 组件、脚本、Prefab、场景对象和验收条件元数据映射为 SourceCandidate；
- adapter 异常映射为结构化错误码。

不得从本模块导入 engine-unity 内部文件。

## ChangeSet

`ChangeSetProposal` 包含 base version、目标 integration/objects、前后值、理由、预期、影响、风险、验证、回滚和审批要求。只有唯一解析且由认证用户确认的 Backpin 可以生成提案。`AIPlaytestService.propose_issue_change` 只返回 `changeset.propose` 命令输入和 owning module；组合层再调用公共 CommandRegistry。此模块没有写文件或调用 Unity mutation 的路径。

Mock 回钉的 `source_record_uri` 指向 `contracts/examples/source-catalog.v1.json` 中与构建版本绑定的记录，因而可以验证候选确实来自该 fixture 的源快照；它不声称本仓库包含真实 Unity 项目源码。Live adapter 必须把候选映射到 owning module 提供的版本化源目录，并保证 project/build/version/locator 一致。

## Frontend composition（Planned）

`frontend/src/index.ts` 导出静态 module contribution、六个懒加载编辑器和带 Zod 输入的命令。根 module-runtime 尚不存在，所以 catalog 生成、OpenAPI TypeScript client、TanStack Query hooks 和 Dockview 实际挂载无法在本工作树验证。编辑器只读取注入的 server read model，执行模式不能由 local state 覆盖；所有操作只调用 `WorkbenchCommandClient`。

前端 `playtest.run` 使用稳定 TestCase/build ID；宿主 `PlaytestCommandApi` 负责通过生成 client 解析为后端 `RunRequest`，组件不得自行 fetch。Live 缺 runner、Cached 缺已验证历史 artifact 时，`canExecute` 会明确拒绝。编辑器本地状态只允许严格列出的视图偏好字段，不能注入执行模式或其他 server truth。

## Repository 与 job runtime

`InMemoryPlaytestRepository` 用于 deterministic Mock，并以 `PlaytestRun.issues` 为 Issue 单一真源；审核会同步回 run。生产 repository 必须提供相同的追加式 run 身份与原子 Issue 更新语义。

`jobs.py`、worker hook 和 workflow YAML 是 core job runtime 的组合入口，不是一个已注册的持久化状态机。接入时必须由 core 实现 queued/running/pause/success/failure/cancel 状态、进度持久化、恢复、重试与幂等；当前缺少 core-kernel/module-runtime，因此该部分为 Blocked。

## 事件

事件 envelope 保留 core-kernel 的 event/project/correlation/causation/actor/mode 字段，payload 由本模块 Pydantic 类型定义，且 envelope mode 必须与 payload/evidence mode 一致；`playtest.issue.backpin.resolved` 只接受真正的 `resolved` backpin。消费者必须按 event ID 幂等处理。当前模块提供事件类型与 JSON Schema，但事件 producer/transport 要由尚未落地的 core module-runtime 接入，不能视为已发布。

## 现场恢复

`workbench.context.restore` 命令携带 issue、run、build、execution mode 以及 scene/object/camera/trajectory/time。宿主必须先定位证据构建；对 Mock 或 Cached 证据，`require_confirmation=true`，不得无提示覆盖当前 Live 工作区上下文。
