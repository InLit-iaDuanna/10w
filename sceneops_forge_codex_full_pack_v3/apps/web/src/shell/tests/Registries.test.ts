import test from 'node:test';
import assert from 'node:assert/strict';
import {
  EMPTY_WORKBENCH_CONTEXT,
  moduleContribution,
  type WorkspaceCoordinator,
} from '../../../../../modules/forge-shell/frontend/src/index.ts';
import { createCommandRegistry } from '../../registries/CommandRegistry.ts';
import { createWorkspaceRegistry } from '../../registries/WorkspaceRegistry.ts';

test('disabling forge-shell hides its presets', () => {
  assert.deepEqual(createWorkspaceRegistry([moduleContribution], new Set()).list(), []);
  assert.equal(
    createWorkspaceRegistry([moduleContribution], new Set(['forge-shell'])).list().length,
    11,
  );
});

test('coordinator-bound shell commands register through the standard app registry', () => {
  const commands = createCommandRegistry(
    [moduleContribution],
    new Set(['forge-shell']),
    { workspaceCoordinator: {} as WorkspaceCoordinator },
  );
  const availability = commands.availability('workbench.open_editor', {
    workbench: EMPTY_WORKBENCH_CONTEXT,
    permissions: new Set(['workbench:write']),
    connectedIntegrations: new Set(),
    source: 'menu',
  }, { editorId: 'fixture' });
  assert.equal(availability.available, true);
});
