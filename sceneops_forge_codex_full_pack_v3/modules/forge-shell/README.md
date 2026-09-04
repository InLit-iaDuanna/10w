# Forge Shell

Forge Shell provides the chat-first SceneOps workbench contract: four edge drawers, Dockview-backed areas, typed editor placement, workspace presets, context binding, layout history, and versioned persistence.

## 用户与体验

新项目首先显示全屏对话编辑器和四条轻量边缘拉手。用户可以通过拖拽、键盘、命令搜索或菜单打开工具。抽屉支持隐藏、临时展开和固定；编辑器支持标签、替换、四向拆分、浮动、弹出、最大化、关闭与恢复。

## Public frontend API

Only `frontend/src/index.ts` is public. It exports:

- shell contracts and the `moduleContribution` manifest;
- `EditorRegistry`, `WorkspaceRegistry`, `WorkbenchCommandBus`, and `WorkbenchEventBus`;
- `EdgeDrawerCoordinator`, `WorkspaceCoordinator`, and layout persistence;
- Home/Judge and the other documented preset templates;
- deterministic mock editors and a recording docking port for tests/examples.

`moduleContribution.createCommands` is the dependency-aware contribution used by the app registry. `createForgeShellModuleContribution(coordinator)` returns the coordinator-bound form with a concrete `commands` array.

Feature modules register editor definitions; the shell never switches on game-domain editor IDs. Editors expose lazy loaders, permissions/integrations, serializable state, context binding, visible error states, and render-suspension policy.

## Commands and events

Public shell commands are `workbench.open_editor`, `workbench.close_editor`, `workbench.reopen_editor`, `workbench.move_editor`, `workbench.switch_editor`, `workspace.undo_layout`, and `workspace.reset`.

Versioned events are documented in [docs/public-contracts.md](docs/public-contracts.md).

## Persistence

Schema version 3 stores editor instances, drawer state and last size, floating/popout groups, context binding, local serializable state, active/maximized area, and an opaque Dockview layout. Version 1 and 2 documents migrate deterministically. An invalid or corrupt workspace document recovers to Home with an explicit reason. If the document metadata is valid but its opaque Dockview snapshot is rejected or describes different container partitions, the production adapter rebuilds and persists the visible layout from that validated metadata and surfaces a recovery notice. Import never mutates the current workspace until validation succeeds.

The versioned on-disk contracts are `schemas/module-manifest-v1.schema.json`, `schemas/shell-events-v1.schema.json`, and `schemas/workspace-layout-v3.schema.json`. Passing the enabled `EditorRegistry` to `LayoutRepository` additionally rejects disabled editor IDs and hydrates each editor state through its registered `restoreState` function.

## Execution modes

- `live`: the production adapter uses pinned `dockview-react@8.2.0`; its edge groups own drawers, tab transfer, floating groups, popouts, resize geometry, and native mutation events.
- `mock`: deterministic editor definitions and `RecordingDockingPort` used by tests and examples.
- `cached`: not used.
- `live`: generated catalog composition with the real conversation editor is available in `apps/labs/shell`.
- `planned`: broader browser/popout verification; this round only ran the minimal conversation proposal → confirmed docking path.

## Setup and tests

Pinned dependencies are recorded in the application-root `pnpm-lock.yaml`. Available verification commands are:

```text
cd modules/forge-shell/frontend
pnpm run typecheck
pnpm test
pnpm run test:bridge
```

Before the latest safety and reconciliation changes, `pnpm run typecheck`, 19 module tests, and 2 bridge tests passed. Those results predate the current code. The added/changed suites are **not run — pending explicit test approval**.

## Limitations

Standalone startup and current limitations are documented in `../../apps/labs/shell/README.md`. Auto-hide edges require dockview-enterprise 8.2.0, used here only in permitted local evaluation with its watermark. The module deliberately does not emulate Dockview pane geometry. `WorkspaceCoordinator` records typed metadata and transaction history; `DockviewPort` owns spatial behavior and exposes a serializable topology projection for native drag/close reconciliation. A blocked popout returns `POPOUT_BLOCKED`, while real cross-window lifecycle and visual behavior remain not run / pending approval.

## Shared contracts

UI types moved to `@sceneops/core-ui`; `frontend/src/index.ts` continues re-exporting them. Manifest uses generated module-runtime snake_case fields. The old shell manifest schema delegates to the canonical module-runtime schema; workspace presets remain a typed frontend contribution. `ShellToolRuntimeContext` supplies existing command handlers to the real Tool Library and Command Search editors.
