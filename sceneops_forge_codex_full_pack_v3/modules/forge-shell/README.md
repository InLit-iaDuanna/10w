# Forge Shell

Forge Shell provides the chat-first SceneOps workbench contract: four edge drawers, Dockview-backed areas, typed editor placement, workspace presets, context binding, layout history, and versioned persistence.

## 用户与体验

统一应用当前使用渐进式工具目录：四边拉出的选择器只显示已经进入现行用户旅程、并有真实承载界面的工具。首批只有「模型与资产」和「环境场景」；其余已注册编辑器继续用于历史布局和兼容入口，但不会自动进入当前工具目录。后续增加能力时显式追加目录项，不再把所有已注册模块自动暴露给用户。独立 Shell 未传入渐进目录时仍保留完整开发目录。

最新统一宿主改用区域内原生 grid split（四边拉手属于各自 editor）。旧 edgeGroups 迁移保留标签，`onRegionSplit` 未配置的独立 Shell 继续兼容旧抽屉。标题选择器在每块区域原位选功能，配色统一聊天中性灰。根 `NESTED_REGION_VERIFICATION.md` 记录最新行为，以下旧抽屉记录为历史。

追加交互：普通拖动为 pinned、无固定 640px 上限；首次打开最小 180px，原生分界线可缩至 12px 并收起。`WorkspaceCoordinator` 可配置 `emptyWorkspaceEditorId` 在最后关闭事务中恢复首页；未配置的独立 Shell 仍允许空白。原生尺寸通知只读回，不重复发起调整。右上角本机诊断与最新测试结果见根 `INTERACTION_POLISH_VERIFICATION.md`；下段为此前一轮记录。

区域拉手支持反向拖动收起：从当前区域边缘向已存在的相邻区域拖动超过 48px，会按指针所在位置识别并关闭对应相邻区域；未保存内容仍需确认，锁定区域不会关闭。

最新功能回归：拉出后直接显示工具搜索与选择列表，最小 180px；尺寸/Peek同步和双击已修复。40 项模块及 25 项 bridge 回归通过，四边真实鼠标路径通过。完整范围和历史类型债见根 `UI_FUNCTIONAL_VERIFICATION.md`。

新项目首先显示全屏对话编辑器和四条轻量边缘拉手。用户可以通过拖拽、键盘、命令搜索或菜单打开工具。抽屉支持隐藏、临时展开和固定；编辑器支持标签、替换、四向拆分、浮动、弹出、最大化、关闭与恢复。

四边空区域拉出后均原位显示功能选择器。选择器默认「当前区域」，选中功能后替换选择器，继续由该区域承载；其他拆分/标签/浮动位置仅在用户主动选择时使用。区域标题栏「选择功能」可原位切换，未保存内容仍需确认。显式原位选择已打开的单例功能会移动既有实例，保留其草稿/上下文，不复制也不跳回另一块区域。

工具库以节点树表达制作路径：主分支固定按「需求规划 → 概念与资产 → 角色与动画 → 世界与逻辑 → 界面、音频与特效 → 渲染 → Unity 构建 → AI 游测 → 版本评审」排列，对话、本地项目和 AI 生产计划放在「项目起点」，工具库、命令搜索和集成状态放在「命令与运维」。窄面板为纵向连线，宽面板利用多列空间但保留 DOM 流程顺序。搜索结果保留所属分支和阶段名，未分类的注册工具收入「扩展工具」，不会从入口丢失。

## Public frontend API

V5 UI 刷新：工具选择器使用中文分组、描述与全文关键词查找，位置选项收进折叠区。命令搜索共用 `tool-picker.css`，没有第二套命令执行逻辑。主应用区域栏改为标题选择器与图标菜单，原 Dockview 标签/边缘结构保留。

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
