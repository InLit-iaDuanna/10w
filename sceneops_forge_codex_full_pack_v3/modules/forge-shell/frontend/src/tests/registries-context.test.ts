import test from 'node:test';
import assert from 'node:assert/strict';
import { EditorRegistry } from '../state/editor-registry.ts';
import { WorkspaceRegistry } from '../state/workspace-registry.ts';
import { WorkbenchCommandBus, CommandRejectedError } from '../commands/workbench-command-bus.ts';
import { WorkbenchEventBus } from '../events/workbench-event-bus.ts';
import { VisibilityCoordinator } from '../state/visibility-coordinator.ts';
import { EMPTY_WORKBENCH_CONTEXT, resolveContext } from '../context/workbench-context.ts';
import { createMockEditor } from '../fixtures/mock-shell-fixtures.ts';
import { HOME_PRESET, JUDGE_PRESET } from '../fixtures/workspace-presets.ts';
import { createShellCommandDefinitions } from '../commands/shell-commands.ts';
import type { WorkspaceCoordinator } from '../state/workspace-coordinator.ts';

test('editor registry exposes structured success and failure states and caches lazy loads', async () => {
  const registry = new EditorRegistry();
  registry.register(createMockEditor('success', { requiredPermissions: ['scene:read'], requiredIntegrations: ['unity'] }));
  registry.register(createMockEditor('failure', { rejectLoad: true }));
  assert.equal(registry.availability('success', {
    permissions: new Set(), connectedIntegrations: new Set(['unity']),
  }).status, 'permission-denied');
  assert.equal(registry.availability('success', {
    permissions: new Set(['scene:read']), connectedIntegrations: new Set(),
  }).status, 'offline');
  assert.equal(registry.availability('success', {
    permissions: new Set(['scene:read']), connectedIntegrations: new Set(['unity']),
  }).status, 'available');
  assert.equal(await registry.load('success'), await registry.load('success'));
  await assert.rejects(registry.load('failure'), /Mock load failed/);
  assert.throws(() => registry.register(createMockEditor('success')), /already registered/);
});

test('workspace registry enforces the chat-only Home invariant and carries Judge preset', () => {
  const registry = new WorkspaceRegistry();
  registry.register(HOME_PRESET);
  registry.register(JUDGE_PRESET);
  assert.equal(registry.get('home').editors[0]?.editorId, 'assistant.conversation');
  assert.equal(registry.get('judge').judgeMode, true);
  assert.throws(() => registry.register({
    id: 'home', title: 'bad', editors: [{ editorId: 'dashboard', placement: { mode: 'tab' } }],
  }), /already registered/);
  const invalidRegistry = new WorkspaceRegistry();
  assert.throws(() => invalidRegistry.register({
    id: 'home', title: 'bad', editors: [{ editorId: 'dashboard', placement: { mode: 'tab' } }],
  }), /conversation/);
});

test('context follows global values or overlays a pinned local context', () => {
  const globalContext = { ...EMPTY_WORKBENCH_CONTEXT, projectId: 'prj_1', sceneId: 'scn_1' };
  const following = resolveContext(globalContext, { mode: 'follow-global' });
  const pinned = resolveContext(globalContext, { mode: 'pinned', context: { sceneId: 'scn_pinned' } });
  assert.equal(following.sceneId, 'scn_1');
  assert.equal(pinned.projectId, 'prj_1');
  assert.equal(pinned.sceneId, 'scn_pinned');
  pinned.selectedAssetIds.push('ast_1');
  assert.deepEqual(globalContext.selectedAssetIds, []);
});

test('visibility signals suspend only hidden render-capable editors', () => {
  const events = new WorkbenchEventBus();
  const received: boolean[] = [];
  events.on('workbench.visibility.changed@1', ({ suspended }) => received.push(suspended));
  const coordinator = new VisibilityCoordinator(events);
  coordinator.update('view', createMockEditor('view', { renderCapable: true }), true);
  coordinator.update('view', createMockEditor('view', { renderCapable: true }), false);
  coordinator.update('view', createMockEditor('view', { renderCapable: true }), false);
  coordinator.update('log', createMockEditor('log'), false);
  assert.deepEqual(received, [false, true, false]);
});

test('typed command bus shares one handler across UI sources and returns structured rejection', async () => {
  const bus = new WorkbenchCommandBus();
  let executions = 0;
  bus.register<{ value: number }, number>({
    id: 'fixture.increment',
    title: 'increment',
    requiredPermissions: ['workbench:write'],
    validate: (input): input is { value: number } =>
      typeof input === 'object' && input !== null && typeof (input as { value?: unknown }).value === 'number',
    canExecute: () => ({ available: true }),
    execute: async (_context, input) => { executions += 1; return input.value + 1; },
  });
  const context = {
    workbench: EMPTY_WORKBENCH_CONTEXT,
    permissions: new Set(['workbench:write']),
    connectedIntegrations: new Set<string>(),
    source: 'assistant' as const,
  };
  assert.equal(await bus.execute('fixture.increment', context, { value: 2 }), 3);
  assert.equal(executions, 1);
  await assert.rejects(
    bus.execute('fixture.increment', { ...context, permissions: new Set() }, { value: 2 }),
    (error) => error instanceof CommandRejectedError && error.code === 'UNAVAILABLE',
  );
});

test('shell command DTOs reject spoofed truth, string booleans, and malformed geometry', () => {
  const commands = createShellCommandDefinitions({} as WorkspaceCoordinator);
  const open = commands.find((command) => command.id === 'workbench.open_editor')!;
  const close = commands.find((command) => command.id === 'workbench.close_editor')!;
  assert.equal(open.validate({ editorId: 'fixture', executionMode: 'cached' }), false);
  assert.equal(close.validate({ instanceId: 'one', confirmed: 'false' }), false);
  assert.equal(open.validate({
    editorId: 'fixture',
    placement: { mode: 'floating', bounds: { left: 0, top: 0, width: -1, height: 200 } },
  }), false);
  assert.equal(open.validate({
    editorId: 'fixture',
    placement: { mode: 'split', direction: 'right' },
    confirmed: true,
  }), true);
});
