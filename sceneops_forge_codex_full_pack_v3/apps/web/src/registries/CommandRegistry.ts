import {
  WorkbenchCommandBus,
  type WorkbenchCommandDefinition,
  type WorkspaceCoordinator,
} from '../../../../modules/forge-shell/frontend/src/index.ts';

export interface CommandModuleContribution {
  manifest: { id: string };
  commands?: readonly WorkbenchCommandDefinition<unknown, unknown>[];
  createCommands?(coordinator: WorkspaceCoordinator): readonly WorkbenchCommandDefinition<unknown, unknown>[];
}

export function createCommandRegistry(
  contributions: readonly CommandModuleContribution[],
  enabledModuleIds: ReadonlySet<string>,
  options: { workspaceCoordinator?: WorkspaceCoordinator } = {},
): WorkbenchCommandBus {
  const bus = new WorkbenchCommandBus();
  for (const contribution of contributions) {
    if (!enabledModuleIds.has(contribution.manifest.id)) continue;
    if (!contribution.commands && contribution.createCommands && !options.workspaceCoordinator) {
      throw new Error(`Module ${contribution.manifest.id} requires a workspace coordinator to bind commands`);
    }
    const commands = contribution.commands ?? (
      contribution.createCommands && options.workspaceCoordinator
        ? contribution.createCommands(options.workspaceCoordinator)
        : []
    );
    for (const command of commands) bus.register(command);
  }
  return bus;
}

export { WorkbenchCommandBus };
