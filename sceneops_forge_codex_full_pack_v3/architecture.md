# SceneOps Forge Architecture

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
