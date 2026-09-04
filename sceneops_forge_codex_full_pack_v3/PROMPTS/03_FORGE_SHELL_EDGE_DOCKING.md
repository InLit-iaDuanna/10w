# 03 — ForgeShell, Four-Edge Pull, Docking, and Workspaces

## Recommended agent / model

Use `shell_ui_builder` with Sol/high. Use a separate read-only `qa_reviewer` after implementation.

## Objective

Implement the Blender-like composable workbench shell: four draggable edge drawers, Dockview areas/editors, floating/popout groups, workspace persistence, and Judge Mode.

## Governing context

You are working on SceneOps Forge. Read the root AGENTS.md, product.md, design.md, architecture.md, MODULE_CONTRACT.md, FRONTEND_INTEGRATION.md, MODEL_ROUTING.md, SUBAGENT_ORCHESTRATION.md, DEFINITION_OF_DONE.md, current STATUS.md, current EXECUTION_PLAN.md, and the nearest module AGENTS.md before editing.

This prompt is standalone and may be used in a fresh Codex conversation. Audit existing work first; do not recreate working functionality. Respect module ownership. Do not change a public contract unexpectedly: stop, document the required change, and ask the principal agent to route an architecture review. Continue from plan to implementation and tests unless a real host-level blocker exists.

Every result must distinguish live, cached, mock, planned, and blocked behavior. Code must remain simple, typed, tested, documented, and modular.


## File ownership

Primary ownership:
- modules/forge-shell/**
- apps/web/src/shell/**
- apps/web/src/registries/** assigned to shell
- shell-specific docs/tests

Do not edit feature editor internals.

## Tasks

1. Use `dockview-react` as the only docking engine.
2. Implement Workspace, Area, Editor, Region, Floating Group, and Popout Window concepts.
3. Implement left/right/top/bottom pull zones with hidden/peek/pinned states, pointer thresholds, keyboard/menu alternatives, pin/unpin, size persistence, and visible Judge Mode handles.
4. Implement EditorRegistry, WorkspaceRegistry, WorkbenchCommandBus, typed shell events, shared context binding, and lazy editor loading.
5. Support add as tab, replace, split four directions, move, join where supported, float, popout, maximize/restore, close/reopen, editor-type switch, and drag between drawer/dock.
6. Implement AreaHeader with mode, context, follow/pin, add, split, float, maximize, more, and close.
7. Persist layouts by schema version and add migrations/invalid-layout recovery.
8. Add Home, Design, Assets, Character, World, Logic, Render, Build, Playtest, Review, and Judge presets. Home remains conversation-only.
9. Implement undo for layout operations and confirm unsaved editor state before close.
10. Lazy-load heavy editors, debounce persistence, avoid remount on resize, and expose hooks for hidden-render suspension.

## Acceptance criteria

- All four screen edges can be pulled open and resized.
- Tools can be docked, tabbed, split, floated, popped out, maximized, closed, restored, and saved.
- The shell contains no game-domain switch statements.
- A new registered editor appears without shell source edits.
- Layout restore and migration are deterministic.
- Judge Mode loads/reset in one action.
- Initial Home stays chat-only.

## Required tests

- edge hidden/peek/pinned
- pointer threshold and keyboard alternative
- editor add placements
- tab move and split
- float/popout/maximize
- layout save/restore/export/import/reset
- schema migration and corrupt-layout recovery
- context follow/pin
- unsaved close confirmation
- lazy loading and editor error boundary
- Judge Mode reset
- no dashboard regression

## Do not

- Do not write a custom docking engine.
- Do not mix layout and domain state.
- Do not hard-code editor components into ForgeShell.
- Do not remount a 3D editor on every resize.
- Do not rely only on hidden corner gestures.

## Return / handoff

- Scope completed
- Files changed
- Public contracts changed
- Tests and exact results
- Live/Mock/Cached status
- Known risks
- Integration instructions
- Recommended next task
