# Forge Shell Integration

1. Build `EditorRegistry` from enabled module contributions.
2. Build `WorkspaceRegistry` from the built-in presets plus validated module presets.
3. Create `LayoutRepository` with the enabled `EditorRegistry`, then load the saved document (or a fresh chat-only Home document) and surface any recovery reason.
4. Create a `BindableDockingPort`, then instantiate `WorkbenchEventBus`, `WorkspaceCoordinator`, and `VisibilityCoordinator` once per application window from that document.
5. Build the command registry with `moduleContribution.createCommands` and `{ workspaceCoordinator }`, or use `createForgeShellModuleContribution(workspaceCoordinator)`. Missing coordinator binding is a startup error rather than a silently empty command registry.
6. Build `ForgeShellRuntime` with `createForgeShellRuntime`, and construct `EdgeDrawerCoordinator` from the active document drawers. `ForgeShell` synchronizes edge changes into `WorkspaceCoordinator`; the host callback only needs to refresh its document snapshot and schedule persistence.
7. Render `ForgeShell`. In `ForgeShell.onDockviewReady`, bind the received `DockviewPort` to `BindableDockingPort`; the shell then restores the document through the real Dockview adapter and mirrors drawer state to Dockview edge groups. A rejected opaque Dockview snapshot is rebuilt from validated workspace metadata and appears as a non-fatal recovery notice; a failed metadata rebuild remains a visible failure.
8. Subscribe to `workbench.layout.changed@1` and schedule `coordinator.snapshot()` through `DebouncedLayoutWriter`. The shell already routes Dockview visibility to `VisibilityCoordinator` and native layout mutation brackets to the coordinator.

Assistant actions use the same command handlers as buttons, menus, keyboard shortcuts, and Tool Library entries. Set `source: "assistant"`; customized layouts must return `confirmation-required` until the user approves the preview.

The current repository has no root React/Vite bootstrap or generated module catalog. Therefore real feature-editor composition is planned, while browser rendering, visual interaction, and cross-window popout verification are blocked. The adapter code itself is live and uses Dockview v8 edge/floating/popout APIs; it is not a simulated docking engine.
