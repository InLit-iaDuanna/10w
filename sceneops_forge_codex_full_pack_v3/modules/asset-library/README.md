# Asset Library

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
