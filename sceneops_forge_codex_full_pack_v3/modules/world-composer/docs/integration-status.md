# World Composer 集成状态

基线 `1d4f0f3` 只有规格文档；没有 `STATUS.md`、`EXECUTION_PLAN.md`、core/runtime、apps、services、integrations 或 examples 实现。本任务没有越权创建这些共享模块。

| 能力 | 状态 | 证据 / 原因 | 下一集成点 |
|---|---|---|---|
| Stable ID、selection、spatial math | Mock complete | `packages/scene-viewer` tests | GLB loader 映射 node extras |
| Camera restore/sync | Mock complete | viewer + Issue tests | React/R3F camera port |
| Overlay registry | Mock complete | viewer tests | renderer overlays |
| Resize/hidden suspension | Mock complete | viewer lifecycle tests | ResizeObserver/tab adapter |
| 九类注解 | Mock complete | round-trip + failure tests | core SpatialAnnotation/OpenAPI mapper |
| Asset placement plan | Planned/Mock tested | no scene mutation; gateway fake | asset-library drop + core ChangeSet |
| Graybox/procedural recipe | Planned/Mock tested | deterministic compiler | approved Unity/Blender adapter |
| 六项 Level Gate | Mock complete | two games + failures/blocked | live snapshots from adapters |
| Find My Way Home world data | Mock complete | key/entrance fixture passes gates | asset, logic, Unity, build/playtest |
| Warehouse Escape reuse | Mock complete | base pass + NavMesh break fixture | real project/build E2E |
| Manifest/catalog/feature flag | Blocked | module-runtime/schema absent | task 01 generated catalog |
| React/R3F 3D editor | Blocked | shell/toolchain absent | shell EditorRegistry binding |
| Fixed camera artifact | Blocked | artifact-store absent | capture adapter + provenance |
| Voice transcription | Blocked | voice/LLM adapter absent | transcript adapter; draft only |
| Blender/Unity mutation | Blocked | vendor adapters absent | implement typed protocol outside UI |
| Cached evidence | Not available | no prior real run exists | only add after a real provenance-backed run |
| Live execution | Not verified | no external tool was called | integration-specific live test |

## Required integration sequence

1. Task 01 freezes core IDs, execution mode, WorkbenchContext, ChangeSet/Approval, event envelope and manifest schema.
2. Generate frontend types; map core `SceneSnapshot`/`SpatialAnnotation` into the module projections without hand-copying network models.
3. Register the eight IDs in generated EditorRegistry/catalog and bind screen models to React `EditorProps`.
4. Connect asset-library drop payload to `createAssetPlacementPlan` and core ChangeSet gateway.
5. Implement artifact/Unity/Blender ports with allowlists, timeout, cancellation, retry, progress, logs, provenance and rollback.
6. Run exact-scene live captures and store real provenance before introducing any cached fixture.
7. Complete hero and Warehouse build/playtest E2E in their owning tasks.
