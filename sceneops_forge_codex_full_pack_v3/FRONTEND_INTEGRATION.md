# SceneOps Forge Frontend Integration Guide

Version: 2.0

## 1. Purpose

This guide defines how to add, replace, or integrate frontend functionality without changing the core shell. The frontend is a chat-first, dockable editor environment assembled from feature modules.

A developer should be able to:

- add a new feature module in one folder;
- register one or more tool editors;
- expose commands that chat and buttons can both invoke;
- consume shared project/scene/build context;
- connect to typed backend APIs;
- handle missing integrations;
- save editor-local state;
- add tests and docs without editing unrelated modules.

## 2. Frontend stack

Default:

- React + TypeScript + Vite;
- dockview-react;
- React Three Fiber + Drei;
- TanStack Query;
- small Zustand stores for transient spatial state;
- React Flow for graphs;
- generated OpenAPI client;
- SSE for run progress;
- Vitest + Testing Library + Playwright.

Do not add a second docking engine, second server-state library, or module-specific API client.

## 3. Composition root

`apps/web` contains:

```text
apps/web/src/
├─ main.tsx
├─ app/
│  ├─ providers.tsx
│  ├─ bootstrap.ts
│  └─ error-boundary.tsx
├─ shell/
│  ├─ ForgeShell.tsx
│  ├─ ConversationHome.tsx
│  ├─ WorkspaceManager.ts
│  ├─ EdgeDrawerController.tsx
│  ├─ AreaHeader.tsx
│  └─ layout-persistence.ts
├─ registries/
│  ├─ generated-module-catalog.ts
│  ├─ EditorRegistry.ts
│  ├─ CommandRegistry.ts
│  └─ WorkspaceRegistry.ts
└─ styles/
   ├─ tokens.css
   └─ base.css
```

Business editors and feature UI do not live here.

## 4. Feature module frontend

```text
modules/<module-id>/frontend/src/
├─ index.ts
├─ manifest.ts
├─ editors/
├─ components/
├─ commands/
├─ hooks/
├─ state/
├─ fixtures/
├─ generated/
└─ tests/
```

The public entry exports a `ModuleContribution`.

```ts
export const moduleContribution: ModuleContribution = {
  manifest,
  editors: [assetFactoryEditor, assetValidationEditor],
  commands: [createAssetSpecCommand, runAssetPipelineCommand],
};
```

模块自己的 `frontend/src/generated/module-manifest.ts` 由 `module.yaml` 生成，公开入口引用该文件，不手抄 manifest。Web composition root 直接消费 `apps/web/src/registries/generated-module-catalog.ts`；运行 `scripts/module-generate` 更新，不手工维护 import 或 feature switch。

## 5. Editor registration

```ts
export interface EditorDefinition<TState = unknown> {
  id: string;
  title: string;
  icon: IconName;
  category: EditorCategory;
  load: () => Promise<{ default: React.ComponentType<EditorProps<TState>> }>;
  defaultPlacement: EditorPlacement;
  minWidth?: number;
  minHeight?: number;
  singleton?: boolean;
  requiredPermissions?: string[];
  requiredIntegrations?: string[];
  optionalIntegrations?: string[];
  serializeState?: (state: TState) => JsonValue;
  restoreState?: (value: JsonValue) => TState;
}
```

Example:

```ts
export const sceneViewportEditor: EditorDefinition<ViewportState> = {
  id: 'scene.viewport.3d',
  title: '3D Viewport',
  icon: 'cube',
  category: 'scene',
  load: () => import('./editors/SceneViewportEditor'),
  defaultPlacement: 'center',
  minWidth: 420,
  minHeight: 280,
  singleton: false,
  requiredPermissions: ['scene:read'],
  optionalIntegrations: ['blender', 'unity'],
  serializeState: serializeViewportState,
  restoreState: restoreViewportState,
};
```

Do not import heavy editor components eagerly.

## 6. Editor props

```ts
export interface EditorProps<TState> {
  instanceId: string;
  contextBinding: ContextBinding;
  localState: TState;
  updateLocalState: (patch: Partial<TState>) => void;
  commands: WorkbenchCommandClient;
  events: WorkbenchEventClient;
  close: () => void;
  setTitle: (title: string) => void;
}
```

Editors do not receive raw Dockview APIs unless the shell-specific operation cannot be represented through the command client.

## 7. Chat-only home

The initial layout fixture contains one editor:

```json
{
  "workspace_id": "home",
  "areas": [
    {
      "editor_id": "assistant.conversation",
      "placement": "center",
      "locked": false
    }
  ],
  "drawers": {
    "left": "hidden",
    "right": "hidden",
    "top": "hidden",
    "bottom": "hidden"
  }
}
```

No module may automatically open on first load unless:

- the user invoked it;
- a saved workspace requires it;
- Judge Mode explicitly preloads it;
- a deep link targets it.

## 8. Opening tools from chat

The assistant returns a structured action, not UI-specific imperative code.

```ts
interface OpenEditorAction {
  type: 'workbench.open_editor';
  editorId: string;
  placement: {
    mode: 'replace' | 'tab' | 'split' | 'floating' | 'popout' | 'drawer';
    direction?: 'left' | 'right' | 'above' | 'below';
    edge?: 'left' | 'right' | 'top' | 'bottom';
    relativeToInstanceId?: string;
  };
  context?: Partial<WorkbenchContext>;
  requireConfirmation: boolean;
}
```

The frontend validates editor availability, permissions, integrations, and placement. The assistant cannot bypass these checks.

## 9. Workbench context

```ts
export interface WorkbenchContext {
  projectId: string | null;
  branchId: string | null;
  sceneId: string | null;
  selectedSceneObjectIds: string[];
  selectedAssetIds: string[];
  activeFeatureId: string | null;
  activeTaskId: string | null;
  activeChangeSetId: string | null;
  activeRenderJobId: string | null;
  activeBuildId: string | null;
  activePlaytestRunId: string | null;
  activeIssueId: string | null;
  cameraPose?: CameraPose;
  timelineTime?: number;
}
```

Binding:

```ts
type ContextBinding =
  | { mode: 'follow-global' }
  | { mode: 'pinned'; context: Partial<WorkbenchContext> };
```

Use context IDs to query server data. Do not place entire server entities in global state.

## 10. Commands

All user and assistant actions share typed commands.

```ts
interface WorkbenchCommandDefinition<TInput, TResult> {
  id: string;
  title: string;
  inputSchema: ZodSchema<TInput>;
  requiredPermissions?: string[];
  requiredIntegrations?: string[];
  canExecute(context: WorkbenchContext, input: TInput): CommandAvailability;
  execute(ctx: CommandExecutionContext, input: TInput): Promise<TResult>;
}
```

Examples:

```text
workbench.open_editor
workspace.reset
project.create
feature.create
asset.pipeline.run
scene.annotation.create
changeset.approve
render.recipe.run
unity.build.run
playtest.run
issue.open_backpin
release.create_candidate
```

A feature component must not duplicate command logic.

## 11. Events

Frontend consumes typed server events:

```text
pipeline.run.started@1
pipeline.node.progressed@1
changeset.waiting_approval@1
render.variant.created@1
build.completed@1
playtest.step.recorded@1
issue.created@1
issue.backpin.resolved@1
integration.health.changed@1
```

Use one event transport client. Modules subscribe through the event registry.

## 12. API client

Backend OpenAPI is the source of truth.

Generation:

```text
Pydantic
→ openapi.json
→ generated TypeScript types/client
→ module hooks
```

Only the shared client handles:

- base URL;
- auth;
- request ID;
- timeout and AbortSignal;
- JSON serialization;
- typed errors;
- API version headers.

No direct `fetch` in module components.

## 13. Query keys

Each module owns a query-key factory exported from its public entry.

```ts
export const assetKeys = {
  all: ['assets'] as const,
  list: (projectId: string, filter: AssetFilter) =>
    [...assetKeys.all, 'list', projectId, filter] as const,
  detail: (assetId: string) => [...assetKeys.all, 'detail', assetId] as const,
};
```

Do not hardcode arrays throughout components.

## 14. Error contract

```json
{
  "code": "INTEGRATION_OFFLINE",
  "message": "Unity is not connected.",
  "details": {"integration_id": "unity"},
  "request_id": "req_...",
  "retryable": true,
  "suggested_actions": ["integration.open", "run.retry"]
}
```

UI behavior depends on `code` and structured fields, not message parsing.

## 15. Editor-local state

Serializable local state examples:

- viewport camera and overlays;
- asset-browser filters;
- graph zoom and selection;
- log filters;
- version comparison choices.

Do not serialize:

- WebGL objects;
- React components;
- network clients;
- AbortControllers;
- large server entities;
- secrets.

## 16. Layout persistence

Persist:

- Dockview layout;
- editor instances;
- drawer state and size;
- floating/popout groups;
- local serializable state;
- pinned context;
- active workspace;
- schema version.

Required behavior:

- debounce writes;
- migrate old schema;
- recover invalid layouts;
- maintain a known default fixture;
- one-click reset;
- private and team-shared layouts.

## 17. Edge drawer integration

A module may contribute Tool Library entries, but the shell owns drawer mechanics.

```ts
interface ToolLibraryEntry {
  editorId: string;
  group: string;
  keywords: string[];
  recommendedEdges?: Array<'left' | 'right' | 'top' | 'bottom'>;
}
```

Do not let modules access drawer DOM directly.

## 18. 3D editor integration

Use the shared `scene-viewer` package for:

- GLB loading;
- resource cache;
- ID mapping;
- selection;
- camera synchronization;
- overlays;
- annotations;
- drag/drop placement;
- capture.

Feature modules provide domain overlays through a registry.

```ts
interface SceneOverlayDefinition {
  id: string;
  label: string;
  isAvailable(context: WorkbenchContext): boolean;
  render(props: SceneOverlayProps): React.ReactNode;
}
```

## 19. Adding a new module

1. Run the module scaffold skill/script.
2. Define `module.yaml`.
3. Add module-level `AGENTS.md` and README.
4. Define backend schemas/routes/services if required.
5. Generate the API client.
6. Register editors and commands.
7. Add fixtures and failure states.
8. Add independent tests.
9. Add module docs.
10. Run manifest, dependency, type, unit, and E2E checks.
11. Regenerate the module catalog.

当前命令：

```bash
scripts/module-scaffold <module-id> --title "..." --description "..."
scripts/module-validate
scripts/module-test <module-id>
scripts/module-generate
scripts/module-generate --check
```

前端可通过 `@sceneops/module-runtime` 的 `resolveFrontendModuleStates` 解析 feature flag、依赖和 missing integration metadata。`disabled` 与 `blocked` 必须显示其中文原因；仅 optional integration 缺失时模块保持 enabled 并显示降级说明。

The shell should not require manual edits beyond generated registration.

## 20. Styling and theme changes

- all colors, spacing, typography, borders, and motion use tokens;
- module CSS must not redefine global tokens;
- editor layouts use shared primitives sparingly;
- do not wrap every section in a card;
- modules may add semantic tokens only through the design-token extension file;
- update `design.md` and token docs when public tokens change.

## 21. Testing a frontend module

Minimum:

- editor registers;
- permissions and integration requirements render correctly;
- loading, empty, success, failure, offline, and retry states;
- command invocation;
- context follow and pin;
- local state serialize/restore;
- module can be disabled;
- no direct external-tool calls;
- no shell internals imported.

## 22. Documentation synchronization

Update in the same commit when relevant:

- `FRONTEND_INTEGRATION.md`;
- module README;
- `docs/editor-registry.md`;
- `docs/workbench-context.md`;
- `docs/tool-window-development.md`;
- `docs/api.md`;
- `docs/events.md`;
- generated TypeScript client.

## 独立 Shell 组合（2026-09-05）

功能回归补充：`DockingGroupTopology.expandedSize` 可选字段表示原生边缘展开尺寸；不以折叠标签栏的 bounding box 覆盖展开记忆。区域 header 高度为 36。Dockview 8.2.0 的公开 setSize 事件缺口通过受控 pnpm patch 修复，应用不直接摆放面板 DOM。短功能选择器只滚动列表，默认当前区域；隐藏面板不参与键盘交互。

V5 视觉更新：应用根 `workbench.css` 提供语义色彩和全局外壳；`forge-shell.css` 提供区域栏/边缘控件；工具库与命令搜索共用模块内 `tool-picker.css`；对话与提供方使用模块内 `unified-ai.css`。标题选择器仍调用原命令，当前区域打开保留 `instanceId`；不新增网络协议、依赖或布局持久化字段。

真实入口：`pnpm lab shell`；初装见 `apps/labs/shell/README.md`。UI 类型统一为 `@sceneops/core-ui` 的 `EditorDefinition`/`EditorHostProps`，Forge Shell 继续转导。ModuleContribution/manifest 来自 module-runtime，manifest 统一使用生成的 snake_case 字段。conversation-home 的默认 placement 为 `{ mode: 'tab' }`，Home preset 决定它独占画布。

`@sceneops/web` 的 `ShellWorkbench` 组合生成目录、EditorRegistry、WorkspaceCoordinator、现有 DockviewPort 和真实对话 runtime。runtime-fixture 在此入口显式禁用。模型选择使用 CodeBuddy CLI API；按钮、搜索、确认后的对话动作都转交已有 WorkbenchCommandBus。代码生成/依赖安装不是完整测试授权。
