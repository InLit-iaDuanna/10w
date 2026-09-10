# SceneOps Forge Frontend Integration Guide

当前新制作主线（2026-09-09）：**SceneOps 对齐目标 → 确认可编辑制作简报与权限 → Codex／CodeBuddy 原生制作 → 工作台接回实际文件、资产和试玩候选 → 准确会话续改**。新工程使用轻量 Three.js / TypeScript / Vite / pnpm 起点。历史任务与编辑服务继续保留；本轮不接 App Server、SDK 或多 Agent 编排。接口、配置与故障处理见 [原生 CLI 制作](modules/ai-agent-runtime/docs/native-cli-production.md)，实际验收见 [验收报告](NATIVE_CLI_PRODUCTION_ACCEPTANCE.md)。

## 首次配置入口（2026-09-08）

Shell 在同一 QueryClient 内组合 Conversation Home 公开 `EnvironmentSetup`，首次自动显示并保留右上角入口；`onOpenChange` 暂停边缘工具教学，配置关闭后再继续。AI 设置中复用同一组件。类型从 `/api/ai/setup` 的 Pydantic/OpenAPI 生成；React 不执行 CLI，安装与登录交给后端固定适配器。详见 [环境配置](modules/conversation-home/docs/environment-setup.md)。

## 2026-09-08：卡片源码精修

卡片源码精修通过 `PlanningJourneyGate.development.renderSourceEditor(projectId, cardId, onDirtyChange)` 组合运行模块公开 `CardSourceEditor`。Design Room 不直接访问源码 API；宿主传入当前卡片身份，组件按身份重置，折叠保留草稿。详见 [接口与范围](modules/ai-agent-runtime/docs/CARD_SOURCE_EDITOR.md)。

Version: 2.0

最新统一宿主启用 `ForgeShell.onRegionSplit`：各 editor 内拉手以原 instanceId 调用 split，新增区域仍用已注册工具库。`DockviewPort.enableRegionSplits` 迁移旧全局边栏；`resizeRegion` 仅调用原生尺寸接口。统一应用不再从四边创建全局抽屉，以下 drawer-change 说明仅适用于兼容入口。详见 `NESTED_REGION_VERIFICATION.md`。

统一宿主可以通过 `ShellToolRuntime.toolLibraryCatalog` 发布一个显式的渐进目录。传入目录后，工具库只显示目录中的已注册 editor，不追加生产全表、系统入口或未分类 editor；不传入时保持完整开发目录。当前产品目录只开放「模型与资产」和「环境场景」，旧 editor 仍可恢复历史布局，但不会自动弹出。

当前交互补充：只有 drawer-change 命令向原生引擎写入边栏尺寸，原生布局通知只同步实际结果，不能在每次 React 渲染后回写尺寸。统一宿主配置 `emptyWorkspaceEditorId`，最后关闭事务恢复中央聊天。UI 调试使用 `apps/web/src/debug` 的字段白名单接口，不记录业务内容。验证见 `INTERACTION_POLISH_VERIFICATION.md`。

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
# 任务级 Agent 追加（2026-09-05）

后续按用户修订：取消聊天/任务模式页，统一输入框中的权限选择决定仅讨论或准备授权卡；`AgentTaskTimeline` 内嵌同一对话。`initialModuleId` 只预选当前工作台已保存上下文，任务暂不附带此草稿。IntegratedModuleHost 默认组合此公开 Agent 界面，旧编辑器首次打开高级区时才加载，加载后关闭不会丢弃未保存草稿。提供方类型包含 `codexcli`，见 `CODEX_PROVIDER_HANDOFF.md`。下文模式页描述为前一增量记录。

`@sceneops/ai-agent-runtime` 公开 `AgentTaskWorkbench` / `AgentTaskActivity`。统一对话负责聊天与 Agent 模式切换，保留两个视图的草稿；项目切换仍遵循未保存提示。服务端状态由 TanStack Query 管理，API 类型来自 `pnpm generate:agent`，不复制网络合同。工具库通过 `ToolRuntime.renderTaskActivity` 组合公开进度视图，不直接依赖运行模块内部实现。

授权卡准备不执行模型和工具；确认后通过同一 AgentTaskService 执行。等待、失败、取消、连接受阻、恢复及核验证据都有 UI；事件按服务端游标逐页读取。当前使用轮询同步持久事件，并非 WebSocket/SSE 推送。详情及真实验收见 `AGENT_LIVE_VERIFICATION.md`。
# 策划旅程组合（2026-09-06）

Shell 通过 Design Room 公开 `PlanningJourneyGate` 为文件夹项目承载策划主对话，未绑定的旧项目继续 `UnifiedConversation`。模型选择器由 Conversation Home 公开导出并通过组合参数传入，不复制提供方配置。文件夹列表使用 workspace-client，策划类型由 `journey.openapi.json` 生成。草稿编辑绑定初始 revision，刷新不静默覆盖本地文档。当前制作卡片只作为计划提案，不映射成已执行生产节点。
# 卡片开发组合端口

Design Room 的 `PlanningJourneyGate.development` 由宿主传入任务准备和时间线渲染函数，保持设计模块不依赖运行模块。共享主输入框区分讨论/开发；prepare仅生成授权卡，不立即执行。任务时间线按选中card_id过滤；退出卡片仍保留项目任务入口。`ProductionAutoOpen` 不为 card-development 任务自动弹出模块页面。

版本管理增量（2026-09-06）：当前功能目录新增 `workbench.version-review`，标题「版本管理」。其 IntegratedWorkbench 默认展示模块自有 VersionTree，旧评审草稿折叠保留；同一项目作用域客户端读取生成的 tree API 类型，不改变初始对话或自动打开工具。

项目聊天公共视图（2026-09-08）：Core UI 公开 ChatComposer（input/options/actions/notice 插槽）与 ChatMessageActions。Design Room 全部阶段和 UnifiedConversation 使用同一实现，业务保留草稿、异步状态、权限和提交回调；chat.css 是公共外观来源，工作流只定义侧栏、预览与定位。

## 2026-09-08：完整项目工具入口

工具库由四项扩展为八项，分为「策划与制作」「游戏内容」「试玩与版本」。新增策划与制作卡片、制作进度、架构与源码、游戏试玩；保留原有四项。策划面板读取大纲和卡片，进入卡片仍使用现有 Journey 命令；源码面板选择登记 worktree 并固定卡片上下文；进度面板按任务折叠详情；试玩复用已有工程状态、构建和预览操作，过期源码不会冒充当前试玩。

环境场景改成无套层边框的画布与可调整高度的资产栏。空场景提供内置资产和导入入口，资产区使用紧凑标题、计数与图标操作。场景对象与资产服务写入语义未修改。

验证：工具分组与搜索 5 项、源码草稿保护、卡片上下文固定、后端源码读取与限定写入最小烟测通过；改动入口定向类型检查。浏览器实际读取当前项目的源码、策划、运行记录与任务列表，并目视检查环境场景及资产空态。本轮没有发起模型生成、保存用户源码、运行构建或试玩。

## 主对话直接制作（2026-09-08）

PlanningJourneyGate.development.prepareProjectDemo 增加 policy（ask/full-access）与 continuation 参数。Design Room 的 discuss_game 只生成问题或制作摘要；set_execution_policy 单独保存用户选择。“开始制作”确认结构化方向后通过宿主进入项目任务，不生成生产卡片。宿主将完全访问映射为 project-demo-agent/agent-full-access 并提交明确授权；询问模式保留 typed-tools 授权。DemoWorkbench 在主对话直接显示原生执行记录与真实运行器预览。

## 多平台导出入口

`build.export` 由 Build Release 贡献，统一宿主注入游戏开发对话交接。Web 导出页面不受旧 Unity 发布工具的连接条件限制，旧发布操作的检查保持不变。对话与项目菜单调用相同打开命令。导出页面使用服务端 SSE 与 TanStack Query；公开类型由 `pnpm generate:exports` 生成。

## 原生导出对话

ExportWorkbench 默认原生创建/发送，显式发送 execution_mode 与 accept_full_access；旧 API 调用缺省保持固定构建/仅讨论。宿主注入 UnifiedModelPicker；同页 SSE 显示 native_runs 实际操作、取消与最终回复。不自动发起额外游戏制作，不混用固定构建下载授权。


## 2026-09-09：中转 GPT 原生执行

完全访问下，OpenAI 兼容中转 GPT 使用 Codex CLI 原生执行，向保存服务的 Responses 接口发送请求。每次独立临时 HOME/CODEX_HOME；真实上游 Key 留在后端，CLI 使用固定目标与模型的临时本地凭据，Shell 不继承该凭据。默认不设总时限、内部模型请求与动作次数不限，可随时停止。

所有项目 Agent 直接显示实际文字、命令、文件与状态。旧 typed 任务保留历史和源码；在相同方向、工作区且无未决写入时，新原生授权可原子接管。未将旧任务改成已成功。

本机 Codex CLI 加本地 Responses 夹具完成真实命令写文件、事件输出与凭据/配置清理；前端原生路由、旧任务交接、对话静态渲染定向冒烟通过。没有调用用户的真实中转模型或构建游戏。组件测试运行器因已有 picomatch 错误未启动。细节见根目录 NATIVE_API_EXECUTION.md。


## 2026-09-09：原生 CLI 制作主线

新游戏制作采用「方向对齐 → 确认可编辑制作简报 → Codex/CodeBuddy 原生会话 → 工作台回流 → 准确会话续改」。权限独立选择 scoped/full；完整权限也需要确认简报。旧任务和领域编辑服务保留，新制作入口不再使用逐动作 JSON 规划器。

工作区级源码登记与任务级 MCP 桥连接真实源码、GLB 资产版本、场景实例和试玩候选；新工程采用所选架构的轻量起点。手动修改后的「更新作品」只执行物化和构建，不调用模型。详见 [原生制作说明](modules/ai-agent-runtime/docs/native-cli-production.md)。

## 初版整理与原工程卡片续改（2026-09-09）

Journey 增加 `organize_production`，`ProductionCard.source_ids` 和可空的 `production_basis`，旧数据缺省兼容。生成结果保持草稿，经现有大纲确认进入 cards；原生来源卡片跳过 Git 分支初始化，旧卡片行为保留。`PlanningJourneyGate.development.renderProductionCard` 注入当前工程源码、按卡片与对话过滤的执行记录和游戏试玩。`prepareProjectDemo` 追加可选 planningCardId，传给 `ContinueProjectDemoRequest.planning_card_id`。服务端从当前策划解析关联内容并核对工作区，写入任务 observations，不接受客户端伪造源码上下文。缺少可续改会话时卡片入口报错，不另建初版任务。

## 消息内记忆（2026-09-09）

Agent Runtime 公开 ExperienceReferences / MemoryMessage；普通对话、策划卡片及任务记录复用同一组件。使用精确 originKey/useKey，任务仅显式聚合自己的调用前缀；运行任务终态触发学习状态刷新。无内容不占位，纠正读取当前版本，历史依据保持原快照。集中管理与来源/撤销说明见 [对话记忆](docs/conversation-memory.md)。
