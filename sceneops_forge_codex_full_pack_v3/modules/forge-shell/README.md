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

工具库改为紧凑的分组列表：不展示流程编号与连线；工具名称、说明和已有状态在同一内容列内，进入箭头保持独立。搜索独占一行，打开位置默认折叠，默认仍原位替换。窄区域单列，宽区域自动分列，低高度区域简化说明并仅滚动列表。统一宿主只保留 Dockview 标签作为工具库标题和关闭入口；业务工具自己的区域栏不变。

2026-09-08 本地浏览器最小 UI 检查：4301 热更新成功；上、下、左、右拉出选择器可用；325px 窄面板的内容、列表和按钮 scrollWidth 均等于 clientWidth；171px 高的上方区域列表独立滚动；搜索过滤、版本管理原位打开并返回工具库通过。未运行完整测试或生产构建。

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


## 2026-09-08：内部抓手与工具图标

区域抓手距离边界 10px，命中区域为 24×64px（横向为 64×24px），编辑器内容预留抓手边距。拖动使用 pointer capture，阻止默认选择和事件冒泡，触摸手势使用 touch-action:none；抓手显示 grab/grabbing 光标。双击、键盘、反向收起沿用现有命令。工具目录支持可选 icon，当前四项使用素材架、Git 分支、立方体和山形场景的 24px SVG 线图标；极窄区域简化说明和图标以保留名称。

本轮浏览器已验证底部与右侧真实拖动：区域数由 2 变为 3，页面视口保持 903×775；工具图标在真实页面显示。网页内部验证不能代替所有原生窗口边缘的系统级命中测试。未运行完整测试或生产构建。


## 2026-09-08：悬停放置（替代按住抓手拖动）

按最新交互要求撤回内移抓手和 34px 编辑器留白，四边改为无常驻短条、无文字提示的轻量悬停区域。鼠标进入边缘显示小卡片，持续停留 650ms 后展开为跟随指针的放置卡片和半透明分区预览；单击才调用原 split 命令确认位置。未激活前移开、激活后离开原区域、窗口失焦、右键或 Esc 均取消。放置层拦截点击，不触发底下的业务按钮。键盘聚焦边缘后 Enter/空格可进入预览。此前按住拖动及反向拖动收起由本交互取代；已有标签关闭入口保留。

验证：`node scripts/frontend-test.mjs apps/web/src/shell/tests/RegionHoverPlacement.test.tsx` 一项通过，覆盖延迟激活、提前离开、指针跟随、确认一次和 Esc 取消。真实 4301 页面检查展开卡片、分区预览与 Esc 取消，编辑器 padding 为 0。完整构建和全量测试未运行。工具目录新图标继续保留。

### 悬停入口范围修订

悬停放置只由 ForgeShell 根工作区承载一个实例，只有左、右、下三个入口；顶部和内部每个编辑器都不再注册入口。预览以完整工作区为范围，新工具区域使用 Dockview 原生根级 group.moveTo 放置到工作区外侧，原生分隔线仍可调整已有面板。定向测试再次通过，并断言入口恰为三个且不存在顶部入口；开发服务器成功编译 Shell。此次浏览器连接超时，未完成根级布局的浏览器复验。

## 首次上手动画

首次进入显示 HTML/CSS 动画：靠近右边缘、停留展开、移动卡片、单击形成分区。点击「我来试一试」关闭遮罩并进入真实操作，工作区左/右/下边缘短暂高亮，提示随 idle/hover/ready 状态变化。只有 split 命令成功才显示完成；失败保留重试。完成或明确跳过保存浏览器本地标记 `sceneops.workspace-edge-intro`，后续访问不自动弹出。未完成试用不会保存完成标记；减少动态效果设置下显示静态示意。

验证：RegionHoverPlacement 与 WorkspaceEdgeIntro 两项定向组件测试通过，覆盖延迟、取消、真实回调确认、失败重试和完成后重新挂载不弹出；真实 4301 浏览器检查引导动画排版及点击试用后的三侧高亮。未在用户项目里自动完成分区练习，预览保留首次引导供用户体验；未运行全量测试或生产构建。

## 项目工具更新

`ToolLibraryCatalogEntry.group` 可选；按首次出现顺序建立分组，保留无分组旧目录行为。当前目录中不为普通工具显示“未执行”任务状态。
