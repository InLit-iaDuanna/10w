# 公共合同

## 领域模型

`CharacterAnimationContractCatalog` 生成以下 JSON Schema：

- `CharacterSpec`：角色、源资产、来源类型、Feature/Task 链接、预期骨骼和坐标系；
- `RigVersion`：独立 Rig 版本 ID、稳定 Bone ID、前一版本、审批和 provenance；
- `SkinVersion`：独立 Skin 版本 ID、目标 Rig、顶点权重样本和审批；
- `AnimationClipSpec`：Clip 版本、时长、采样率、Loop、Root Motion、首尾姿态、事件和脚掌接触样本；
- `RetargetProfile`：源/目标 Rig 和显式骨骼映射；
- `AnimatorStateSpec`：Clip 引用和 typed transitions；
- `PreviewArtifact`：固定相机、媒体类型、帧数/时长、artifact URI、回归基线/分数、模式和 provenance；
- `UnityCharacterMapping`：角色、Rig、Skin、Clip、Prefab、GameObject、Controller、ChangeSet 与来源 provenance 链；
- `ChangeSet`：基线、前后值、影响/风险、验证/回滚计划、审批要求和 dry-run 标志。

JSON Schema：`contracts/manifests/character-animation.schema.json`。所有未知字段都会被拒绝；时间戳归一为 UTC；距离使用米；坐标系显式声明。

## HTTP API

| 方法与路径 | 结果 |
|---|---|
| `GET /integrations` | 导入路径和可选集成状态 |
| `POST /inspect` | `CharacterInspectionResult` |
| `POST /versions/compare` | 可逆 `RigVersionDiff` 或 `ClipVersionDiff` |
| `POST /versions/review` | 审批记录和回退版本 ID |
| `POST /previews/capture` | `PreviewArtifact` |
| `POST /previews/retarget` | Profile 检查与可选预览 |
| `POST /previews/compare` | 固定相机回归结果 |
| `POST /unity-mappings/propose` | `planned` Mapping + ChangeSet |
| `POST /unity-mappings/execute` | 适配器执行结果；未批准返回 409 |

错误是平铺结构：`code`、`message`、`details`、`request_id`、`retryable`、`suggested_actions`。离线返回 503；审批冲突返回 409；无效版本返回 400。

## 事件

所有事件使用统一 envelope、UTC 时间、correlation/causation ID 和明确执行模式：

| 事件 | 合同 Producer（接入 event bus 后） | 预期 Consumer |
|---|---|---|
| `character.inspected@1` | CharacterAnimationService / inspect job | Production Planner、Observability |
| `rig.version.approved@1` | 版本 review handler | Asset Library、Unity integration |
| `animation.clip.approved@1` | 版本 review handler | World/Logic、Unity integration |
| `animation.preview.captured@1` | preview job | Artifact Store、Review workspace |
| `unity.character.mapping.applied@1` | Unity adapter job | engine-unity、Observability、Build Release |

事件 Schema 位于 `contracts/events/`。表中的 producer/consumer 是公开集成合同；当前 core event bus 不存在，因此没有对外发布的 live 事件。

## 兼容规则

- 现有 stable ID 的语义不可变；复制产生新 ID，重命名保留 Bone ID。
- 破坏性 payload 变化必须发布事件或合同新版本。
- 前端不得手抄网络模型；运行 `npm run generate:api` 从 OpenAPI 生成。
- 其他模块只导入 `frontend/src/index.ts`、后端包 `__init__.py` 或文档化的 adapter/service protocol。
