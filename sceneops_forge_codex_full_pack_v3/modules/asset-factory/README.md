# Asset Factory

`CardAssetWorkflow.observeConversation` 默认开启，使主对话中的新一轮模型描述触发一次真实草稿更新。独立的模型工具区将它设为 `false`，只读取并操作同一产物，避免主对话预览与停靠工具同时观察消息而重复发起 Blender 作业。

Asset Factory turns a canonical AssetSpec and source `.blend` file into reviewed,
validated GLB/FBX artifacts and an immutable AssetVersion. One versioned workflow
is reused by the Find My Way Home key and Warehouse Escape obstacle fixtures.

## 卡片模型工作流（2026-09-06）

制作卡片现在有两条接入当前 Git 卡片工作树的真实路径：

- **导入**：选择 GLB 或 FBX，点击“导入并检查”后由 Blender 5.1 读取；原文件保留，另存 `.blend`、可交互预览 GLB、Unity 交换 FBX 和 manifest。
- **场景投放导入**：把一个或多个 GLB / FBX 直接拖入 3D 世界预览，会复用同一导入检查，成功版本自动存入项目资产库并加入当前场景。
- **新建**：复用卡片的唯一建模对话。每条新用户回答请求一份结构化修改方案，并由固定 Blender 工作器用允许的 cube、sphere、cylinder、cone 更新真实草稿；右侧 Three.js 面板随成功结果刷新。第一次生成 v1，后续回答在同一会话资产上追加版本，旧版本保留。
- **归一化**：填写目标最大边（米）后另存新版本，统一缩放、水平居中并落到 Z=0；不覆盖原文件或旧版本。

实时请求以 `project_id + card_id + session_id + trigger_message_id` 唯一识别。相同消息的已完成结果直接复用，不会重复调用模型或 Blender；失败后必须显式设置重试。组件挂载时把已有历史作为基线，只处理随后出现的新消息，因此刷新或重新打开长对话不会补跑旧内容。

工作流不自动提交或合并 Git，不运行游戏、构建、渲染或 Demo。CodeBuddy CLI 支持文字方案；其当前非交互合同没有本地参考图参数，所以带参考图时需选择 Codex CLI 或支持视觉输入的 OpenAI 兼容模型，不能自动换提供方。当前没有自动执行 GLB 压缩；压缩继续作为显式后续动作。

网络合同由 `contracts/card-assets.openapi.json` 和生成的 TypeScript 类型承载；运行 `pnpm generate:card-assets` 更新。实际产物在当前卡片分支的 `assets/models/<card_id>/<asset_id>/` 下，执行日志留在应用 `.local` 数据目录。

## Workflow

```text
preflight -> clean -> uv/material -> LOD -> collider -> turntable/AOV
          -> validate -> export -> publish
```

Optional LOD/collider nodes report a state and reason; they never silently skip.
Geometry, UV/material, and stable-identity gates are blocking. Failed gates stop
before export and publication.

## Mutation safety

Every execution accepts an `AssetChangeSet` carrying base version, previous and
proposed values, rationale, impact/risk, validation, rollback, and approval
requirements. `dry_run=true` produces a `planned` preview and does not call an
adapter. A non-dry run pauses in `waiting_approval` unless the ChangeSet is
approved. Before any Blender call, the service verifies the complete ChangeSet
and normalized command scope against a server-owned approval record and resolves
the project root from trusted project metadata. Before mutation, a versioned
`.blend` snapshot is created. Failures after that point trigger a typed rollback
command.

Blender exports first land under the run-owned `.sceneops/asset-factory/`
directory. Publication validates those bytes, creates the final GLB, FBX, and
manifest with no-clobber semantics, verifies them through the catalog artifact
boundary, and removes only newly created files if catalog publication fails.
Failed publication also discards its finalized candidate so a corrected retry is
not poisoned by stale metadata.

Idempotency is explicit: the service requires an injected request-ledger port.
The bundled in-memory implementation atomically reserves run IDs and caller keys,
and replays a prior terminal result only for the exact same validated request.
Reusing a key for different input fails with `IDEMPOTENCY_CONFLICT`; cancellation
is accepted only for a reserved run, so an unknown ID cannot plant a future
cancel. The Blender worker separately binds retry records to the complete command
in server-owned operation storage outside project content.

## Public surface

- Python: `asset_factory` exports pipeline contracts, `AssetPipelineService`,
  request-ledger/finalized-candidate ports and in-memory adapters, jobs, and
  `create_router`.
- TypeScript: `frontend/src/index.ts` exports the lazy Asset Factory/Validation
  contributions, visible run-state builder, and `importProjectAssetFile` for host-owned scene drop flows.
- Blender: only the public `sceneops_blender` typed adapter is accepted.
- Asset catalog: only public `asset_library` models/service are used.

## Execution modes

- `live`: bundled bridge actually invoked Blender now.
- `cached`: a result loaded from trusted live-run storage, keyed by workflow slot
  plus operation, and bound to the normalized full command and current source
  checksum. Verified blobs materialize each new run's working/output paths and
  are checked for size and checksum before use.
- `mock`: deterministic fixture adapter; Blender not invoked.
- `planned`: dry-run only.
- `blocked`: requested Blender integration is unavailable.

Selection is explicit. The live service does not silently auto-fallback.

## Tests

```text
PYTHONPATH=modules/asset-library/backend/src:integrations/blender-addon/src:modules/asset-factory/backend/src python3 -m unittest discover -s modules/asset-factory/backend/tests -v
node --test modules/asset-factory/frontend/src/tests/*.test.ts
```

卡片路径的最小真实 Blender 烟测是显式 opt-in：

```text
SCENEOPS_REAL_BLENDER_SMOKE=1 node scripts/python.mjs -m unittest modules.asset-factory.backend.tests.test_card_asset_workflow_smoke.CardAssetWorkflowSmoke.test_real_generate_import_and_normalize -v
```

它只在临时 Git 工程中检查新建、GLB/FBX 导入和归一化；不会写当前用户项目。实时多版本和真实 CodeBuddy → Blender 链路分别由 `test_real_live_dialogue_versions` 与 `test_real_codebuddy_live_dialogue_to_blender` 覆盖，并且都需要显式环境变量才运行。

## Known limitations

This starting commit had no core ChangeSet package, module runtime, durable run
ledger, remote artifact store, API composition root, generated TypeScript client,
Unity module, or Blender executable. The module-local Pydantic ChangeSet is an
explicit public asset-domain contract pending core adoption; distributed
idempotency and finalized-candidate persistence, shell/OpenAPI/Unity wiring, and
a filesystem-isolated Blender worker are `planned`. Direct subprocess transport
refuses project `.blend` inputs; the current host reports Blender `blocked`
unless an executable is explicitly configured.

## 概念与资产独立工作台

`apps/labs/concept-assets/README.md` 提供一条命令启动的 Web/API。新增公开 `ConceptAssetHandoff`、`asset_spec_from_concept`、`ConceptAssetLab`、`LabAction`、`LabSnapshot`、`create_lab_router`；工厂声明依赖 concept-lab，消费其公开批准草稿，不导入模块内部文件。前端公开 `ConceptAssetsWorkbench`，实际调用原领域服务。所有外部适配器固定 mock，未启动 Blender 或渲染。本轮测试仅见入口烟测记录；原测试套件 not run / pending approval。

统一应用现公开 `loadIntegratedWorkbench()`；空态、自有草稿、样例边界与验证限制见 [统一编辑器说明](docs/unified-workbench.md)。
