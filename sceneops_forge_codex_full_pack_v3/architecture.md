# SceneOps Forge Architecture

当前新制作主线（2026-09-09）：**SceneOps 对齐目标 → 确认可编辑制作简报与权限 → Codex／CodeBuddy 原生制作 → 工作台接回实际文件、资产和试玩候选 → 准确会话续改**。新工程使用轻量 Three.js / TypeScript / Vite / pnpm 起点。历史任务与编辑服务继续保留；本轮不接 App Server、SDK 或多 Agent 编排。接口、配置与故障处理见 [原生 CLI 制作](modules/ai-agent-runtime/docs/native-cli-production.md)，实际验收见 [验收报告](NATIVE_CLI_PRODUCTION_ACCEPTANCE.md)。

首次环境配置（2026-09-08）：Conversation Home 拥有向导与 `/api/ai/setup` 路由，AI Provider 公开 `CLISetup` 负责固定工具安装与官方终端登录；CodeBuddy 集成公开的路径解析器供两个提供方的对话和 Agent 执行共同使用。安装目录与全局 CLI 隔离，工作台优先读取独立安装。Shell 仅组合入口，沿用本地令牌、Origin 校验与生成客户端。详见 [环境配置](modules/conversation-home/docs/environment-setup.md)。

## 1. Architecture goals

- full-chain 3D game production without a monolithic codebase;
- one module folder per independent capability;
- chat-first shell with dockable tools;
- stable contracts across Blender, Web, Unity, rendering, builds, and tests;
- adapters isolate vendor/tool behavior;
- modules can be developed by separate Codex conversations or subagents;
- code remains easy to replace, test, and document;
- live, cached, and mock execution are explicit.

## 2. System layers

```text
┌──────────────────────────────────────────────────────┐
│ Chat-First ForgeShell                                │
│ Conversation · Edge Drawers · Areas · Editors        │
├──────────────────────────────────────────────────────┤
│ Feature Modules                                      │
│ Project · Asset · World · Logic · Render · Test      │
├──────────────────────────────────────────────────────┤
│ Core Kernel                                          │
│ IDs · Context · Commands · Events · Jobs · Approval  │
├──────────────────────────────────────────────────────┤
│ Control Plane                                        │
│ API · Persistence · Pipeline · Policy · Provenance   │
├──────────────────────────────────────────────────────┤
│ Tool Adapters                                        │
│ Blender · Unity · ComfyUI · Git · Storage · LLM      │
└──────────────────────────────────────────────────────┘
```

## 3. Monorepo

```text
apps/
  web/
  desktop-bridge/
services/
  api/
  orchestrator/
packages/
  core-contracts/
  core-events/
  core-auth/
  core-storage/
  core-ui/
  scene-viewer/
  test-kit/
modules/
  <module-id>/
integrations/
  blender-addon/
  unity-package/
  comfyui-adapter/
examples/
  remember-home/
  warehouse-escape/
docs/
```

`apps` and `services` are composition roots. Business behavior belongs to modules or core packages.

## 4. Static module runtime

SceneOps uses build-time explicit module discovery, not an unrestricted runtime plugin loader.

Flow:

```text
modules/*/module.yaml
→ schema validation
→ dependency graph validation
→ generated frontend module catalog
→ generated backend module catalog
→ application boot
```

Benefits:

- deterministic builds;
- type safety;
- clear ownership;
- no arbitrary third-party code execution;
- modules can still be disabled through flags and permissions.

### 4.1 Module contributions

A module may contribute:

- editors;
- commands;
- events;
- backend routers;
- jobs;
- workflows;
- policy gates;
- permissions;
- migrations;
- fixtures;
- documentation;
- WorkBuddy skills.

### 4.2 Dependency direction

```text
modules -> core packages
modules -> declared public API of another module
apps/services -> module registries
integrations -> core adapter contracts
```

Forbidden:

- module internal import from another module;
- app shell importing module implementation details;
- integration SDK imported directly into UI modules;
- circular module dependencies.

## 5. Frontend architecture

```text
ForgeShell
├─ ConversationHome
├─ EdgeDrawerController
├─ WorkspaceManager
├─ EditorRegistry
├─ WorkbenchCommandBus
├─ WorkbenchEventBus
├─ WorkbenchContext
└─ LayoutPersistence
```

### 5.1 State ownership

| State | Owner |
|---|---|
| server entities and jobs | TanStack Query |
| transient selection/camera/drag | small Zustand stores |
| Dockview layout | WorkspaceManager |
| editor-local serializable state | editor instance |
| module enablement | ModuleRuntime |
| authenticated user and permissions | core-auth |

### 5.2 Command flow

```text
Chat / Button / Shortcut / Menu
→ Typed WorkbenchCommand
→ CommandRegistry
→ Permission + Preconditions
→ Module handler
→ API or local shell action
→ Typed result/event
→ UI update
```

Chat never bypasses the CommandRegistry.

### 5.3 Tool opening

```text
OpenEditorCommand
→ validate module enabled
→ validate integration/permission
→ resolve placement
→ create editor instance
→ Dockview update
→ persist layout
```

## 6. Backend architecture

```text
FastAPI composition root
├─ core APIs
├─ generated module router registry
├─ domain services from modules
├─ repositories
├─ job orchestration
├─ event stream
└─ adapter gateway
```

A route validates and delegates. It does not contain business logic.

Each module backend may contain:

- router;
- schemas;
- service;
- repository;
- jobs;
- policy gates;
- tests.

## 7. Core kernel

Core kernel owns only cross-cutting primitives:

- IDs and identity mappings;
- user/project/workbench context;
- Artifact and ArtifactProvenance;
- TypedCommand envelope;
- TypedEvent envelope;
- ChangeSet and Approval primitives;
- Job/Run identity and execution modes;
- permissions;
- standard errors;
- pagination and timestamps.

Domain-specific fields stay in feature modules.

## 8. Persistence

Development:

- SQLite;
- local content-addressed artifact directory;
- Redis optional but recommended for queue/events.

Deployment:

- PostgreSQL;
- Redis;
- S3/MinIO-compatible artifact store;
- Git/Git LFS for project source and large assets.

Artifacts are immutable by checksum. New content creates a new version.

## 9. Events

Event envelope:

```json
{
  "event_id": "evt_...",
  "event_type": "asset.version.published",
  "event_version": 1,
  "occurred_at": "2026-09-04T00:00:00Z",
  "project_id": "prj_...",
  "correlation_id": "corr_...",
  "causation_id": "cmd_...",
  "actor": {"type": "user", "id": "usr_..."},
  "mode": "live",
  "payload": {}
}
```

Rules:

- event schemas are versioned;
- events are append-only facts;
- consumers are idempotent;
- event names use past tense;
- commands express intent, events express outcomes;
- breaking changes require a new event version.

## 10. Jobs and pipelines

Pipeline definitions reference module jobs by stable IDs.

```text
PipelineDefinition
├─ nodes
├─ edges
├─ conditions
├─ approval pauses
├─ retry policies
└─ cache policies
```

Core states:

```text
queued -> running -> waiting_approval -> succeeded
                        ↘ failed / cancelled / rolled_back
```

A module job receives typed input and returns typed artifacts/results.

## 11. Adapters

Canonical interface concept:

```ts
interface ToolAdapter<TCapability, TCommand, TResult> {
  healthCheck(): Promise<IntegrationHealth>;
  capabilities(): Promise<TCapability>;
  dryRun(command: TCommand): Promise<ChangePreview>;
  execute(command: TCommand, signal: AbortSignal): Promise<TResult>;
  validate(result: TResult): Promise<GateResult[]>;
  rollback?(snapshotId: string): Promise<RollbackResult>;
}
```

Adapters must not leak vendor SDK types into domain modules.

## 12. Blender identity and export

```text
AssetSpec / SceneObject
→ Blender custom properties
→ export manifest
→ glTF extras / FBX sidecar
→ Web viewer
→ Unity package
```

Maintain separate IDs for:

- source asset;
- source object;
- published asset version;
- scene instance;
- Unity Prefab;
- Unity GameObject instance.

The identity map records their relationships.

## 13. Unity runtime bridge

The Unity package supplies:

- SceneOpsIdentity component;
- project/scene scan;
- import hooks;
- Prefab publishing;
- component command allowlist;
- test/build operations;
- runtime telemetry bridge;
- playtest action interface;
- evidence capture;
- issue backpin metadata.

## 14. Render pipeline

```text
RenderBrief
→ deterministic AOV capture
→ RenderRecipe
→ AI service
→ variant artifacts
→ human approval
→ typed editable writeback
→ deterministic validation capture
```

AI images are proposals unless an approved mapping writes real parameters or assets back into Blender or Unity.

## 15. AI playtest

The game exposes bounded actions and observations:

```text
reset(testCase)
getObservation()
getAvailableActions()
executeAction(action)
getGameState()
getGoalProgress()
captureEvidence()
```

Each step records the build, scene, actor pose, game state, action, target `sceneops_id`, outcome, progress, and evidence.

## 16. Security boundaries

- application runtime cannot execute arbitrary scripts;
- adapters validate project-root paths;
- commands are allowlisted and schema-validated;
- secrets remain outside artifacts and logs;
- external tools default to localhost;
- destructive actions require explicit approval;
- downloaded assets are scanned and provenance-tagged;
- plugin/module manifests do not execute code by themselves;
- sandbox and permission settings are documented.

## 17. Offline and judge modes

Three execution modes:

- live tool path;
- cached real-run replay;
- deterministic mock path.

Judge Mode uses cached evidence for long operations and runs at least one short live action when available. Every mode is visible.

## 18. V5 implemented foundation (2026-09-05)

The preceding sections describe the product target, not evidence that external paths work. V5 extends the same Web/API with a canonical `packages/harness-kernel` and eight bounded AI modules. `integrations/ai-provider` owns CLI/Chat Completions transport and endpoint-bound write-only secrets. Module APIs remain the composition boundary; Pydantic/OpenAPI owns network contracts.

The implemented flow is: explicit project context → user-requested intent/plan generation → persisted proposal → validation and manual start → sequential registered capabilities → durable runs/events → observation and optional recovery proposal/template draft. Model output cannot choose authority or grant production permissions. Planning and recovery requests are separate from Run accounting and disclosed as such.

Only project reading, draft reading and structured expert assessment have V5 handlers. Thirteen external capability declarations have no handler and remain planned/blocked. Advanced graph/cached execution, automatic graph repair, multi-party compensation and second-project template replay are not implemented. Unknown provider usage remains unknown; bounded-calls is explicit, durable and distinct from verified monetary budgeting.

Workspace SQLite also holds provider metadata, model tiers, proposals and derived records. The kernel owns its run/event/lock tables. Secrets live in an owner-only file adjacent to the database. Startup creates empty schema and marks interrupted dead-process runs; it never launches work or imports demo records. Dock layout remains browser-local.

API startup and schema generation use `scripts/python-workspace.mjs` to load only the checked-in local sources declared by requirements, avoiding editable-install `.pth` behavior. This is development package resolution, not runtime plugin discovery.

See `V5_HANDOFF.md`, `V5_SMOKE.md`, `CURRENT_CAPABILITY_CATALOG.md` and `PROTOTYPE_GAP_MATRIX.md` for the delivered scope and unverified behavior.
# 任务授权执行补充（2026-09-05）

完整 CLI 模式是显式授权的新增高风险能力 `codex.task.execute`，复用 TaskService/Harness，而非修改默认受限模型边界。卡片/任务/grant 持久绑定模式，固定一次 CLI 调用、20 分钟；内部模型次数未知。任务级审批覆盖 CLI 原生执行，不保证逐文件 ChangeSet 或全机隔离；结果标待审阅。授权范围作为独立 developer 指令进入 CLI，不只是 UI 提醒。见 `CODEX_PROVIDER_HANDOFF.md`。

提供方扩展：`sceneops_ai_provider` 内部 Codex CLI transport 保持同一 generate/structured 合同，`codexcli` 模型独立持久化；配置从后端生成到前端，应用权限不随 provider 放宽。单 Agent 输入按权限使用讨论或原 TaskService，不引入第二套执行服务。见 `CODEX_PROVIDER_HANDOFF.md`。

`sceneops_ai_agents.AgentTaskService` 管理任务授权和跨 run 预算；每次模型决策、类型化工具动作均复用 `sceneops_harness`。任务与事件写入 SQLite，ChangeSet/审批/执行记录保持原 Harness 合同。应用只组合公开路由和生命周期。

模型无文件路径、Shell 或任意代码权限。工具会话按服务端 grant 绑定独立 `agent-workspaces/<project_id>`，Blender 使用受限本地 socket 和 OS 沙箱，Unity 使用私有 mailbox 与编辑器主线程 dispatcher。Unity 自有包从固定随附代码路径加载，产物仍被限制在独立工程；不是全进程 OS 沙箱。最终成功需实时双端身份/尺寸/console 回读。未明确的写入结果停止，不盲目重复。

健康状态通过 `AgentTaskService.execution_status()` 读取应用跟踪的生命周期，不探测或启动工具；外部手动关闭进程在下次真实工具读回中确认。真实验证及剩余边界见 `AGENT_LIVE_VERIFICATION.md`。
# 单人策划旅程增量（2026-09-06）

新文件夹项目以 workspace 公开存储接口绑定本地根目录。Design Room 的 PlanningJourneyService 拥有单人策划状态、消息、大纲和制作卡片提案，不执行生产任务。模型只由明确命令调用，沿用 ProviderService。持久导出记录衔接 SQLite 与项目内 JSON，最终提交使用 revision 比较，快照仅在用户确认后创建。旧项目继续原有路径。详细协议与局限见 `PLANNING_JOURNEY_STAGE1.md`。

## 本地多平台导出

Build Release 持有导出任务、持久记录及平台适配器；AI Agent Runtime 提供有界结构化导出对话；API 和 Web 宿主组合二者。共享 Web 快照后分别运行 Capacitor / Electron 本地构建。参见 [导出交付](PLAYABLE_EXPORTS_MILESTONE.md)。


## 2026-09-09：中转 GPT 原生执行

完全访问下，OpenAI 兼容中转 GPT 使用 Codex CLI 原生执行，向保存服务的 Responses 接口发送请求。每次独立临时 HOME/CODEX_HOME；真实上游 Key 留在后端，CLI 使用固定目标与模型的临时本地凭据，Shell 不继承该凭据。默认不设总时限、内部模型请求与动作次数不限，可随时停止。

所有项目 Agent 直接显示实际文字、命令、文件与状态。旧 typed 任务保留历史和源码；在相同方向、工作区且无未决写入时，新原生授权可原子接管。未将旧任务改成已成功。

本机 Codex CLI 加本地 Responses 夹具完成真实命令写文件、事件输出与凭据/配置清理；前端原生路由、旧任务交接、对话静态渲染定向冒烟通过。没有调用用户的真实中转模型或构建游戏。组件测试运行器因已有 picomatch 错误未启动。细节见根目录 NATIVE_API_EXECUTION.md。


## 2026-09-09：原生 CLI 制作主线

新游戏制作采用「方向对齐 → 确认可编辑制作简报 → Codex/CodeBuddy 原生会话 → 工作台回流 → 准确会话续改」。权限独立选择 scoped/full；完整权限也需要确认简报。旧任务和领域编辑服务保留，新制作入口不再使用逐动作 JSON 规划器。

工作区级源码登记与任务级 MCP 桥连接真实源码、GLB 资产版本、场景实例和试玩候选；新工程采用所选架构的轻量起点。手动修改后的「更新作品」只执行物化和构建，不调用模型。详见 [原生制作说明](modules/ai-agent-runtime/docs/native-cli-production.md)。

## 对话记忆整合（2026-09-09）

ai-run-distiller 通过公开来源与项目状态回调聚合记忆；Design Room 保持决定的唯一存储，Conversation Home/Agent Runtime 提供自身持久来源。制作准备与对话复用同一有界提供快照，事件关联消息、任务、批次与修订。类型从 Pydantic/OpenAPI 生成；事务、幂等及验证边界见 [对话记忆](docs/conversation-memory.md)。
