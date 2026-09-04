export interface ForgeShellManifest {
  schemaVersion: 1;
  id: 'forge-shell';
  version: string;
  title: string;
  description: string;
  status: 'active';
  featureFlag: 'forge_shell';
  dockingEngine: 'dockview-react';
  requires: { modules: string[]; integrations: string[]; optionalIntegrations: string[] };
  contributes: { editors: string[]; commands: string[]; events: string[]; workspacePresets: string[] };
  permissions: string[];
  entrypoints: { frontend: string };
}

export const manifest: ForgeShellManifest = {
  schemaVersion: 1,
  id: 'forge-shell',
  version: '0.1.0',
  title: 'Forge Shell',
  description: 'Chat-first workbench shell, edge drawers, editor orchestration, and versioned workspaces.',
  status: 'active',
  featureFlag: 'forge_shell',
  dockingEngine: 'dockview-react',
  requires: {
    modules: ['core-kernel', 'module-runtime', 'conversation-home'],
    integrations: [],
    optionalIntegrations: [],
  },
  contributes: {
    editors: ['shell.tool-library', 'shell.command-search'],
    commands: [
      'workbench.open_editor',
      'workbench.close_editor',
      'workbench.reopen_editor',
      'workbench.move_editor',
      'workbench.switch_editor',
      'workspace.undo_layout',
      'workspace.reset',
    ],
    events: [
      'workbench.editor.opened@1',
      'workbench.editor.closed@1',
      'workbench.editor.load_failed@1',
      'workbench.layout.changed@1',
      'workbench.visibility.changed@1',
      'workbench.context.binding_changed@1',
      'workbench.drawer.changed@1',
    ],
    workspacePresets: ['home', 'design', 'assets', 'character', 'world', 'logic', 'render', 'build', 'playtest', 'review', 'judge'],
  },
  permissions: ['workbench:read', 'workbench:write'],
  entrypoints: { frontend: './frontend/src/index.ts' },
};
