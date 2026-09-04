# VFX/Shader 集成契约

## 入口

Python 消费者只能从 `vfx_shader` 导入公共 dataclass、枚举、服务与 Protocol。前端组合根只能从 `frontend/src/index.ts` 导入 `moduleContribution` 和公共类型。

## Unity 边界

`UnityVfxAdapter` 是结构化 Protocol，集成 ID 统一为 `unity`，提供 `health_check`、`capabilities`、`dry_run` 和 `publish`。命令仅包含白名单动作 `publish_vfx_recipe` 或 `set_vfx_enabled`、稳定项目/对象 ID、Recipe 版本及 ChangeSet ID。适配器不得泄漏 Unity SDK 类型。

发布前依次校验：模块启用、`vfx:publish` 权限、Recipe、预算、ChangeSet 已审批、base/Recipe 版本、ChangeSet 目标与 Recipe 影响对象完全一致、Unity 在线且支持所需能力、health/capability 均声明规范 `unity` ID、dry-run 成功。绑定启停只向 Unity 发送选中绑定的单个稳定目标。成功结果仍需匹配项目、目标、Recipe ID/版本，并携带 result/artifact ID、UTC 时间与有效 64 位 checksum；否则作为非阻塞失败。失败返回结构化 `OperationResult`，不抛出外部 SDK 错误，并且不阻塞核心构建。

## Render 边界

`RenderPreviewAdapter` 同样提供能力、健康、dry-run 与 render，并要求 health/capability 都声明规范 `render` ID。Render 只用于可选外部预览；离线不会影响 Recipe 编辑、Mock 预览或核心构建。当前实现没有 live Render 适配器。

## ChangeSet 与 AI 提案

当前根 `core-kernel` 尚无可导入 runtime，因此模块以完整本地值对象实现 ChangeSet：base version、目标集成/对象、前后值、理由、预期结果、影响范围、风险、验证/回滚计划及审批要求均为必填。审批会记录结构化内容快照；发布必须精确匹配 shader、质量档、参数、预算与全部 bindings，单项启停必须精确匹配 binding ID、目标和布尔值。只有 `proposed → approved` 后可发布或启停，审批后任何内容替换都会失败。根公共类型可用后应直接替换该值对象。AI 来源的 Recipe 在未审批时必定返回 `CHANGESET_APPROVAL_REQUIRED`；只有适配器成功发布后才发出 `vfx.recipe.published@1`，并把返回 provenance 明确更新为 `published` 且保留真实执行模式。

模块事件构建器接收 `EventContext`，输出根 envelope：`event_id`、`event_type`、`event_version`、`occurred_at`、`project_id`、`correlation_id`、`causation_id`、`actor`、`mode` 和 `payload`。模块 schema 校验这一完整 envelope。

## 事件绑定

绑定使用稳定 `binding_id`、`event_name`、`target_sceneops_id` 与布尔 `enabled`。示例事件是数据，而不是模块间内部导入。发布或启停成功后发出 JSON Schema 验证的过去时事件。

## 添加第二个游戏

复制 `fixtures/warehouse_escape.json` 的数据形状，替换稳定 ID、参数、事件名与 provenance 即可。不得在平台源码中加入游戏名分支。
