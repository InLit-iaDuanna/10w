# 集成说明

## Unity 边界

Audio Studio 只依赖公开的 `EngineUnityAudioAdapter` 协议：`get_capabilities()`、`health_check()`、`dry_run_audio_mapping()` 和 `publish_audio_mapping()`。结果带执行模式、适配器版本、结构化状态及可选 provenance。`unity` 是可选集成：没有 Unity 时仍可创建、分析和审查提案；适配器实现属于 `engine-unity`，本模块既不引用其内部路径，也不修改 Unity 文件。

`AudioMapping` 绑定稳定的音频资产 ID、事件 ID、目标 `sceneops_id`、`AudioSource` 名称和 Mixer 组。两个英雄流建议：

| 事件 | 目标对象 | Mixer 组 |
| --- | --- | --- |
| `gameplay.key.picked_up` | `so_key_home_01` | `SFX/Interact` |
| `gameplay.door.unlocked` | `so_door_home_01` | `SFX/Environment` |

`ChangeSet` 的生命周期为 `draft → submitted → approved/rejected → applied`。资产发布使用 `artifact-store / publish_audio_asset` 并精确绑定资产 ID、来源版本和已有 checksum；Unity 映射使用 `unity` 并精确绑定一个 `so_` 目标。两类审批不能互换。ChangeSet 还包含前后值、预期结果、影响范围、风险、验证/回滚计划和审批要求。审批调用由可信宿主提供 approver、UTC 时间与证据，并记录当时的结构化内容；审批后任何内容替换都会阻止执行。映射操作验证基线、目标对象、绑定资产、AudioSource、clip 与 Mixer 均匹配，适配器结果也必须回传同一组身份。dry-run 可以在 draft 状态下验证提案但不发布；发布操作要求 `approved`、资产状态为 `published`，以及完整 provenance（类型、来源版本/提交、相关 `sceneops_id`、工具/适配器/配方、创作者、模式、时间、审批状态与 SHA-256 值）。AI 来源还必须记录 provider、model、workflow hash、正提示词、seed、相关参数，以及使用过的负提示词。否则服务拒绝操作，绝不调用适配器。

超时、取消、重试、结构化日志与真实 Unity 的补偿由 `engine-unity` 适配器所有并必须由其实现；本模块在没有该实现时只运行明确标注为 mock 的协议测试。

前端命令暂用本模块的运行时 `inputSchema.parse` 与 gateway `execute` 表面，让聊天和按钮走同一处理函数；core runtime 可用后应替换为其公开命令类型。

## 第二游戏模板

`warehouse_escape_template()` 提供 `gameplay.switch.activated` 与 `gameplay.exit.unlocked` 的同一结构。替换项目数据、对象 ID、音频资产和 Mixer 组即可复用；不需要更改本模块源代码。

## 事件

所有事件采用过去式，版本为 1：`audio.spec.created@1`、`audio.asset.inspected@1`、`audio.event.bound@1` 和 `audio.mapping.published@1`。每个事件记录 correlation、causation、UTC 时间和执行模式。
