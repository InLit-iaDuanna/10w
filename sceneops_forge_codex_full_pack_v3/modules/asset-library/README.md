# Asset Library

## 内置资产浏览界面

内置资产默认展示自适应缩略图网格，按完整场景、建筑与物件、角色分类。搜索、美术形式、场景主题及游戏方向筛选集中在列表上方；点击卡片进入详情，返回列表保留筛选。详情保留 3D 预览、项目导入、下载及生成参考，全部使用工作台主题色。

## 固定内置资产

公开 `BuiltinAssetCatalog`／`create_builtin_asset_router` 提供随包安装的 877 项原创资产：原有 SceneOps Haven Kit 102 项，以及 Atlas100 v2 的 675 个模型和 100 个场景。`GET /api/builtin-assets` 返回聚合目录并保留每个条目的素材包 ID、版本和许可；各 ID 下 `/glb`、`/preview`、`/lod/{level}`、`/physics` 与场景条目的 `/scene` 返回已登记文件。`POST /{id}/adopt` 通过组合根注入的 Asset Factory 导入服务生成项目版本。前端 `loadBuiltinAssetLibrary()` 懒加载固定资产浏览界面，编辑器 ID 为 `asset.builtin-library`。目录与素材保留在安装包内，各项目采用时复制，不修改原件。

Atlas100 v2 条目保留 UV0／UV1、PBR 通道、三级 LOD、物理绑定以及适用模型的骨骼与动作元数据。素材包摘要同时公开受限的原始清单与资源基址，供同源加载 512px PBR 图和运行时模块。其 555 个场景专属单体没有独立静态缩略图，列表明确使用所属场景图作为参考；进入详情后的实时 3D 仍加载单体 GLB。原有资产继续按 CC0-1.0 提供，Atlas100 v2 按包内 MIT 许可提供。

Asset Library is the canonical catalog and publication boundary for SceneOps 3D
assets. It keeps source assets, source objects, immutable published versions,
scene usage, Unity import state, including builds, licenses, and provenance in one
queryable record.

## Users and tools

Artists and technical artists use **Asset Browser** (`asset.browser`) to search
and filter assets. **Asset Inspector** (`asset.inspector`) exposes dimensions,
triangles, materials, textures, UV, rig, animations, LODs, collider, license,
AI provenance, scene instances, Unity state, and builds. The editors are lazy
module contributions and never open on the chat-only home automatically.

## Public surface

- Python: `asset_library` exports the Pydantic contract models,
  `InMemoryAssetRepository`, `AssetLibraryService`, and `create_router`.
- Unified project catalog: `ProjectAssetCatalogService`,
  `SqliteProjectAssetRepository`, and `create_project_catalog_router` store the
  model versions explicitly adopted from a production card. A catalog entry
  keeps its source asset identity while each `.blend`, preview GLB, and FBX
  version is immutable. Re-saving the exact same source version is idempotent.
- TypeScript: `frontend/src/index.ts` exports the module contribution, browser
  query model, filters, query keys, and inspector-state builder.
- Command intents: `asset.search`, `asset.version.publish`.
- Event: `asset.version.published@1`.

### 统一旅程中的项目资产库

统一工作台把已采用的项目资产显示为正方形缩略卡片。卡片只展示简单对象名、版本和主要尺寸；点击后才进入单资产编辑页，查看真实 GLB、源文件、版本、几何信息、重命名和“加入场景”等详细操作。场景实例的位移、旋转和缩放仍属于 World Composer，不混进资产卡片。

面向用户的名称会整理成简短对象名，例如“大树”“岩石”“僵尸”。导入文件名或模型返回的长标题保存在 `source_title` 供追溯，不再占据资产库标题；同一项目重名时使用稳定的数字后缀。用户重命名通过乐观版本字段防止覆盖较新的修改。

统一后端公开以下项目级接口，界面与 Agent/CLI 适配器调用的是同一套服务，不存在只在前端生效的操作：

- `GET /api/project-assets?project_id=...`：读取项目资产卡片；
- `PUT /api/project-assets/{entry_id}?project_id=...`：修改简单名称；
- `POST /api/card-assets/{record_id}/save-to-library`：把明确采用的模型版本存入资产库；
- `GET /api/card-assets/files/{artifact_id}`：读取已登记的源文件或预览产物。

每次“新建模型”或“导入 GLB / FBX”都会创建新的 `modeling_session_id`。新会话只继承项目技术栈、策划背景和世界尺度，不继承上一件资产的聊天记录或未确认草稿。

The module owns asset catalog records. It stores external scene, Unity, and build
identifiers as stable references; it does not mutate those systems.

## Publication rules

A version is publishable only when trusted finalized-run storage resolves the
exact `(asset_id, asset_version_id, change_set_id)` candidate, a server-owned
authority verifies its approval scope, trusted storage verifies every artifact
size/checksum, all catalog-owned required gates exist, and every blocking gate
passes. All three boundaries deny by default when the composition root omits
them. The public request carries IDs and approval evidence, never a caller-built
candidate. Publication inserts a new immutable `AssetVersion`; source files are
never overwritten.
Artifact SHA-256 values are required because immutable artifact verification and
provenance cannot be provided by a filename or database version alone.

## Integration and degraded behavior

`artifact-store` is required by the assembled application but the domain service
can be tested with the in-memory repository. Unity is optional. If it is absent,
the inspector displays `unavailable` rather than claiming import success.
Loading, empty, permission denied, disconnected, failed/retry, and success states
are explicit view models.

## Setup and tests

From the specification root:

```text
PYTHONPATH=modules/asset-library/backend/src python3 -m unittest discover -s modules/asset-library/backend/tests -v
node --test modules/asset-library/frontend/src/tests/*.test.ts
```

Fixture records are under `fixtures/` and are always labelled `mock`.

## Example

```python
from asset_library import AssetLibraryService, AssetSearchFilter

results = service.search(AssetSearchFilter(query="key", has_collider=True))
```

## Known limitations

The unified project catalog is wired to the card-model workflow and the
Three.js environment scene. It catalogs actual local files but does not by
itself publish them to Unity, a build, or an external artifact store. The older
formal publication boundary and its stronger approval/provenance requirements
remain separate.

## 独立工作台整合

资产库在 `apps/labs/concept-assets/` Web 中可搜索与检查，使用公开 AssetLibraryService 和原发布验证。该入口隔离 mock 数据，重启重置；启动和最小烟测结果见入口 README，原全量测试本轮 not run / pending approval。

### 原生 Blender 源

项目版本增加 `source_kind='blender'`、`parent_source_version`、`node_ids` 和 `operation='blender-edit'`。这一源类型保留实际 `.blend` 与 GLB 路径，FBX 可空，不携带可编辑 DoorRecipe。旧 `file` 类型要求不变。`register_version(expected_version=...)` 在登记时核对旧版本，并通过 SQLite 事务检查防止另一服务覆盖较新目录版本；同一版本的相同内容仍幂等。

## 实时预览调校

选择资产后直接进入 3D 工作区；含动画的角色默认播放 Walk。右侧可切换待机、走路、跑步、挥手，调整播放速度（0.25–2 倍）、动作强度（与静止姿态混合）、循环、朝向、曝光、主光和背景；支持网格及骨架显示。底部时间轴可暂停并拖到指定姿势。

“保存调校”按资产 URL 保存在当前浏览器，包含显示参数和相机位置；通过“读取已保存”恢复。调校只影响预览，不写回 GLB 或动画源文件。页面隐藏、暂停和离开预览会停止动画帧循环；窗口缩放与控制器调整不会重新加载模型。

## 原生 GLB 版本

`ProjectAssetVersion.source_kind` 新增 `glb`：真实 GLB 源路径、稳定版本 ID 和 render 运行产物必填，不要求伪造 `.blend` 或 `.fbx`。原生制作通过运行模块的任务工具桥校验、保存并登记版本；目录继续使用 `expected_version` 检查冲突，场景引用保持独立且显式更新。旧 file、procedural、blender 版本兼容。

## 本地项目目录与外部制品存储

本地项目资产目录通过 SQLite 和项目内文件服务运行，读取、版本保存及原生材质编辑不依赖外部 artifact-store。该集成列为可选；远程发布仍使用原有发布策略与服务检查，本次没有改变质量或发布权限。
