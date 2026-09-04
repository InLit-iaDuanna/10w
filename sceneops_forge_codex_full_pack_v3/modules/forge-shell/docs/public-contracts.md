# Forge Shell Public Contracts

## Architecture boundary

Feature modules contribute `EditorDefinition` objects and optional workspace presets. The application creates registries from public contributions, then provides them to the shell. Feature editors do not receive raw Dockview APIs.

`DockingEnginePort` is the only spatial boundary. The production adapter is backed by `dockview-react`. The coordinator owns command validation, metadata, history, dirty/locked policy, and persistence; Dockview owns geometry, tab rendering, drag/drop, four edge groups, floating groups, and browser popouts. `describe()` projects Dockview's live group graph into `DockingTopology`, allowing user-originated native mutations to be reconciled as one coordinator transaction.

## Visible editor states

Every editor can resolve to `loading`, `empty`, `ready`, `offline`, `permission-denied`, `failed`, or `disconnected`. `EditorRegistry.availability` returns structured missing permissions and integrations so the host can render a Chinese user-facing explanation and retry/open-integration actions without parsing messages.

Lazy-load failures are represented as `EDITOR_LOAD_FAILED`. They are observable through `workbench.editor.load_failed@1` and must be rendered by the application error boundary.

The editor host supplies both the saved `contextBinding` and its resolved `WorkbenchContext`, together with the shared command and event clients. Local state, title, and binding changes emit layout-change notifications so the application persistence writer can save them.

## Commands

| Command | Result |
|---|---|
| `workbench.open_editor` | opens after registry/permission/integration checks and optional assistant confirmation |
| `workbench.close_editor` | rejects locked editors and requests confirmation for dirty editors |
| `workbench.reopen_editor` | restores the most recently closed serializable instance |
| `workbench.move_editor` | moves between Dockview groups or an edge drawer without remount intent |
| `workbench.switch_editor` | replaces an instance's editor type after availability checks |
| `workspace.undo_layout` | restores the previous metadata and Dockview snapshot |
| `workspace.reset` | loads a named preset; dirty state requires user confirmation, while same-Judge reset remains one action |

Command inputs are exact DTOs. Unknown fields, string booleans, invalid placement discriminators, and non-finite/non-positive geometry are rejected. `executionMode` is not accepted from command input; only a trusted workflow call may override the coordinator's live default. Assistant-originated mutation calls cannot self-confirm a customized layout: a user-originated command must execute the approved operation.

## Events

| Event | Version | Payload summary |
|---|---:|---|
| `workbench.editor.opened` | 1 | instance, placement, source |
| `workbench.editor.closed` | 1 | serializable closed instance |
| `workbench.editor.load_failed` | 1 | instance, editor ID, structured error |
| `workbench.layout.changed` | 1 | workspace ID and operation |
| `workbench.visibility.changed` | 1 | instance ID and visible/suspended state |
| `workbench.context.binding_changed` | 1 | instance ID and follow/pinned binding |
| `workbench.drawer.changed` | 1 | edge, hidden/peek/pinned state, and size |

Events use the shared workbench envelope at the application boundary. This module's local bus carries typed event name and payload only; the core runtime supplies identity, actor, correlation, causation, mode, and UTC timestamp.

## Edge interaction

The default thresholds are 12px reveal, 80px Peek, 220px Pin, and below 48px reverse-hide. Shift opens pinned, Alt requests a floating Tool Library, double-click toggles the last open size, Escape dismisses Peek globally, and menu/keyboard commands explicitly select hidden, Peek, or pinned. The pointer zones span all four full edges at 12px; Judge Mode keeps them visibly labelled at 36px. Drawers are Dockview edge groups, so a panel retains its identity and render host when dragged between an edge and the main dock.

## Persistence and recovery

`LayoutRepository.load` returns a discriminated result: restored, migrated, missing, or recovered. Invalid workspace documents use a fresh known preset and report `CORRUPT_JSON`, `UNSUPPORTED_SCHEMA`, or `INVALID_LAYOUT`. A structurally valid document can still contain a Dockview snapshot that Dockview rejects or whose container partitions disagree with canonical metadata; `DockviewPort.restoreWorkspace` then clears the partial graph, deterministically materializes the validated workspace metadata, and returns `recovered` so `ForgeShell` persists the rebuilt snapshot and shows a recovery notice. Export is stable pretty JSON. Import validates before returning a document. Writes are debounced through `DebouncedLayoutWriter`.

Layout history frames contain both the workspace document and the recent-close stack. Replace performs an atomic container-slot substitution. Native Dockview close/move uses `beginDockviewMutation` / `completeDockviewMutation`; unknown panels, locked moves/removals, and dirty removals are rejected by restoring the pre-mutation Dockview snapshot. Programmatic spatial operations resolve their target from Dockview's active panel (including edge, floating, and popout groups) and adopt Dockview's complete topology after the operation.

## Hidden render suspension

Editors declare `renderPolicy: "suspend-when-hidden"`. The host reports active-tab visibility; `VisibilityCoordinator` emits `workbench.visibility.changed` only when effective visibility changes. Feature render loops subscribe through the editor host hook and stop work while suspended.
