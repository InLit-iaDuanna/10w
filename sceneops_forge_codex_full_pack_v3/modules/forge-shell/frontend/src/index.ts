export * from './contracts.ts';
export { manifest } from './manifest.ts';
export { EditorRegistry } from './state/editor-registry.ts';
export { WorkspaceRegistry } from './state/workspace-registry.ts';
export { WorkbenchCommandBus, CommandRejectedError } from './commands/workbench-command-bus.ts';
export { createShellCommandDefinitions } from './commands/shell-commands.ts';
export { WorkbenchEventBus } from './events/workbench-event-bus.ts';
export { EMPTY_WORKBENCH_CONTEXT, resolveContext, setContextBinding } from './context/workbench-context.ts';
export {
  EdgeDrawerCoordinator,
  DEFAULT_EDGE_THRESHOLDS,
} from './state/edge-drawer-coordinator.ts';
export {
  WorkspaceCoordinator,
} from './state/workspace-coordinator.ts';
export type {
  OpenEditorRequest,
  OpenEditorResult,
  CloseEditorResult,
  LayoutMutationAuthorization,
  LayoutMutationResult,
} from './state/workspace-operations.ts';
export {
  createWorkspaceFromPreset,
} from './state/workspace-factory.ts';
export type { IdentifierFactory } from './state/workspace-factory.ts';
export {
  LayoutRepository,
  DebouncedLayoutWriter,
  CURRENT_LAYOUT_SCHEMA_VERSION,
  exportLayout,
  importLayout,
  migrateLayout,
  validateWorkspaceDocument,
} from './state/layout-persistence.ts';
export type {
  LayoutEditorRegistry,
  LayoutLoadResult,
  LayoutStorage,
} from './state/layout-persistence.ts';
export { VisibilityCoordinator } from './state/visibility-coordinator.ts';
export { SHELL_EDITOR_DEFINITIONS, toolLibraryEditor, commandSearchEditor } from './state/shell-editor-definitions.ts';
export {
  BUILT_IN_WORKSPACE_PRESETS,
  HOME_PRESET,
  JUDGE_PRESET,
  createDefaultDrawers,
} from './fixtures/workspace-presets.ts';
export {
  MOCK_EXECUTION_MODE,
  RecordingDockingPort,
  createMockEditor,
  createPresetMockEditors,
  deterministicIdentifierFactory,
} from './fixtures/mock-shell-fixtures.ts';

import { manifest } from './manifest.ts';
import { createShellCommandDefinitions } from './commands/shell-commands.ts';
import { SHELL_EDITOR_DEFINITIONS } from './state/shell-editor-definitions.ts';
import { BUILT_IN_WORKSPACE_PRESETS } from './fixtures/workspace-presets.ts';
import type { WorkspaceCoordinator } from './state/workspace-coordinator.ts';

export const moduleContribution = {
  manifest,
  editors: SHELL_EDITOR_DEFINITIONS,
  createCommands: createShellCommandDefinitions,
  workspacePresets: BUILT_IN_WORKSPACE_PRESETS,
} as const;

export function createForgeShellModuleContribution(coordinator: WorkspaceCoordinator) {
  return {
    manifest,
    editors: SHELL_EDITOR_DEFINITIONS,
    commands: createShellCommandDefinitions(coordinator),
    workspacePresets: BUILT_IN_WORKSPACE_PRESETS,
  } as const;
}
