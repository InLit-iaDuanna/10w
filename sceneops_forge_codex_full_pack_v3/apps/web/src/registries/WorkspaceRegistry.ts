import {
  BUILT_IN_WORKSPACE_PRESETS,
  WorkspaceRegistry,
  type WorkspacePreset,
} from '../../../../modules/forge-shell/frontend/src/index.ts';

export interface WorkspaceModuleContribution {
  manifest: { id: string };
  workspacePresets?: readonly WorkspacePreset[];
}

export function createWorkspaceRegistry(
  contributions: readonly WorkspaceModuleContribution[],
  enabledModuleIds: ReadonlySet<string>,
): WorkspaceRegistry {
  const registry = new WorkspaceRegistry();
  if (enabledModuleIds.has('forge-shell')) registry.registerAll(BUILT_IN_WORKSPACE_PRESETS);
  for (const contribution of contributions) {
    if (!enabledModuleIds.has(contribution.manifest.id)) continue;
    for (const preset of contribution.workspacePresets ?? []) {
      if (BUILT_IN_WORKSPACE_PRESETS.some((builtIn) => builtIn.id === preset.id)) continue;
      registry.register(preset);
    }
  }
  return registry;
}

export { WorkspaceRegistry };
