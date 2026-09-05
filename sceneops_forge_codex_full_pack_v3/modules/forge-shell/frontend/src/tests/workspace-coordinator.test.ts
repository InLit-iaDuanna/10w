import test from 'node:test';
import assert from 'node:assert/strict';
import { EditorRegistry } from '../state/editor-registry.ts';
import { WorkspaceRegistry } from '../state/workspace-registry.ts';
import { WorkbenchEventBus } from '../events/workbench-event-bus.ts';
import {
  WorkspaceCoordinator,
} from '../state/workspace-coordinator.ts';
import { createWorkspaceFromPreset } from '../state/workspace-factory.ts';
import { BUILT_IN_WORKSPACE_PRESETS, HOME_PRESET } from '../fixtures/workspace-presets.ts';
import {
  RecordingDockingPort,
  createMockEditor,
  createPresetMockEditors,
  deterministicIdentifierFactory,
} from '../fixtures/mock-shell-fixtures.ts';
import { validateWorkspaceDocument } from '../state/layout-persistence.ts';

function setup() {
  const editors = new EditorRegistry();
  editors.registerAll(createPresetMockEditors());
  editors.register(createMockEditor('fixture.two'));
  editors.register(createMockEditor('fixture.three'));
  editors.register(createMockEditor('fixture.singleton', { singleton: true }));
  editors.register(createMockEditor('fixture.offline', { requiredIntegrations: ['unity'] }));
  editors.register(createMockEditor('fixture.denied', { requiredPermissions: ['scene:read'] }));
  editors.register(createMockEditor('fixture.load-failure', { rejectLoad: true }));
  const workspaces = new WorkspaceRegistry();
  workspaces.registerAll(BUILT_IN_WORKSPACE_PRESETS);
  const ids = deterministicIdentifierFactory();
  const document = createWorkspaceFromPreset(HOME_PRESET, editors, ids);
  const engine = new RecordingDockingPort();
  const events = new WorkbenchEventBus();
  const coordinator = new WorkspaceCoordinator({
    document,
    editors,
    workspaces,
    events,
    engine,
    environment: { permissions: new Set(['workbench:write']), connectedIntegrations: new Set() },
    createId: ids,
  });
  return { coordinator, engine, events };
}

test('tab, replace, and four split placements update metadata and delegate geometry', async () => {
  const { coordinator, engine } = setup();
  const tabResult = await coordinator.openEditor({ editorId: 'fixture.two', placement: { mode: 'tab' }, source: 'menu' });
  assert.equal(tabResult.status, 'opened');
  assert.equal(coordinator.snapshot().areas[0]?.tabs.length, 2);

  for (const direction of ['left', 'right', 'above', 'below'] as const) {
    await coordinator.openEditor({ editorId: 'fixture.three', placement: { mode: 'split', direction }, source: 'keyboard' });
  }
  assert.equal(coordinator.snapshot().areas.length, 5);

  const activeBefore = coordinator.snapshot().areas.find(
    (area) => area.areaId === coordinator.snapshot().activeAreaId,
  )?.activeInstanceId;
  const replaced = await coordinator.openEditor({
    editorId: 'fixture.two',
    placement: activeBefore
      ? { mode: 'replace', relativeToInstanceId: activeBefore }
      : { mode: 'replace' },
    source: 'button',
  });
  assert.equal(replaced.status, 'opened');
  assert.equal(Object.values(coordinator.snapshot().instances).filter((item) => item.editorId === 'fixture.three').length, 3);
  assert.equal(engine.calls.filter((call) => call.operation === 'open').length, 6);
});

test('selecting an existing singleton replaces the picker in its drawer without losing state', async () => {
  const { coordinator, engine } = setup();
  const existing = await coordinator.openEditor({ editorId: 'fixture.singleton', source: 'button' });
  const picker = await coordinator.openEditor({ editorId: 'fixture.two', placement: { mode: 'drawer', edge: 'left' }, source: 'button' });
  assert.equal(existing.status, 'opened');
  assert.equal(picker.status, 'opened');
  if (existing.status !== 'opened' || picker.status !== 'opened') return;
  coordinator.setDirty(existing.instance.instanceId, true);
  const result = await coordinator.switchEditor(picker.instance.instanceId, 'fixture.singleton');
  assert.equal(result.status, 'focused');
  const document = coordinator.snapshot();
  assert.deepEqual(document.drawers.left.tabs, [existing.instance.instanceId]);
  assert.equal(document.instances[existing.instance.instanceId]?.dirty, true);
  assert.equal(document.instances[picker.instance.instanceId], undefined);
  assert.equal(Object.values(document.instances).filter(item => item.editorId === 'fixture.singleton').length, 1);
  assert.ok(engine.calls.some(call => call.operation === 'move'));
});

test('in-place selection reuses the drawer panel identity and size', async () => {
  const { coordinator, engine } = setup();
  const picker = await coordinator.openEditor({ editorId: 'fixture.two', placement: { mode: 'drawer', edge: 'left' }, source: 'button' });
  if (picker.status !== 'opened') throw new Error('Fixture did not open');
  coordinator.syncDrawer({ ...coordinator.getDrawer('left'), mode: 'pinned', size: 360, lastOpenSize: 360 });
  const before = coordinator.getDrawer('left');
  const result = await coordinator.switchEditor(picker.instance.instanceId, 'fixture.three');
  assert.equal(result.status, 'opened');
  assert.deepEqual(coordinator.getDrawer('left'), before);
  assert.equal(coordinator.getInstance(picker.instance.instanceId)?.editorId, 'fixture.three');
  assert.ok(engine.calls.some(call => call.operation === 'switch'));
});

test('in-place singleton selection still requires confirmation before replacing dirty content', async () => {
  const { coordinator, engine } = setup();
  await coordinator.openEditor({ editorId: 'fixture.singleton', source: 'button' });
  const target = await coordinator.openEditor({ editorId: 'fixture.two', source: 'button', placement: { mode: 'drawer', edge: 'right' } });
  if (target.status !== 'opened') throw new Error('Fixture did not open');
  coordinator.setDirty(target.instance.instanceId, true);
  const before = coordinator.snapshot();
  const result = await coordinator.openEditor({ editorId: 'fixture.singleton', source: 'button',
    placement: { mode: 'replace', relativeToInstanceId: target.instance.instanceId } });
  assert.deepEqual(result, { status: 'confirmation-required', reason: 'unsaved-editor' });
  assert.deepEqual(coordinator.snapshot(), before);
  assert.ok(!engine.calls.some(call => call.operation === 'move'));
});

test('move to drawer/dock, join, float, popout, maximize, switch, close, and reopen work', async () => {
  const { coordinator, engine } = setup();
  const first = await coordinator.openEditor({ editorId: 'fixture.two', placement: { mode: 'split', direction: 'right' }, source: 'menu' });
  const second = await coordinator.openEditor({ editorId: 'fixture.three', placement: { mode: 'split', direction: 'below' }, source: 'menu' });
  assert.equal(first.status, 'opened');
  assert.equal(second.status, 'opened');
  if (first.status !== 'opened' || second.status !== 'opened') return;

  await coordinator.moveEditor(first.instance.instanceId, { mode: 'drawer', edge: 'right' });
  assert.deepEqual(coordinator.snapshot().drawers.right.tabs, [first.instance.instanceId]);
  await coordinator.moveEditor(first.instance.instanceId, { mode: 'tab', relativeToInstanceId: second.instance.instanceId });
  assert.equal(coordinator.snapshot().drawers.right.tabs.length, 0);

  await coordinator.openEditor({ editorId: 'fixture.two', placement: { mode: 'floating' }, source: 'menu' });
  assert.equal(coordinator.snapshot().floatingGroups.length, 1);
  await coordinator.openEditor({ editorId: 'fixture.two', placement: { mode: 'popout' }, source: 'menu' });
  assert.equal(coordinator.snapshot().popoutGroups.length, 1);

  const areas = coordinator.snapshot().areas;
  await coordinator.joinAreas(areas[1]!.areaId, areas[0]!.areaId);
  assert.equal(coordinator.snapshot().areas.length, areas.length - 1);
  await coordinator.toggleMaximize(coordinator.snapshot().areas[0]!.areaId);
  assert.ok(coordinator.snapshot().maximizedAreaId);
  await coordinator.toggleMaximize(coordinator.snapshot().areas[0]!.areaId);
  assert.equal(coordinator.snapshot().maximizedAreaId, null);

  await coordinator.switchEditor(first.instance.instanceId, 'fixture.singleton');
  assert.equal(coordinator.snapshot().instances[first.instance.instanceId]?.editorId, 'fixture.singleton');
  const closed = await coordinator.closeEditor(first.instance.instanceId);
  assert.equal(closed.status, 'closed');
  const reopened = await coordinator.reopenEditor();
  assert.equal(reopened.status, 'opened');
  assert.ok(engine.calls.some((call) => call.operation === 'move'));
  assert.ok(engine.calls.some((call) => call.operation === 'join'));
  assert.ok(engine.calls.some((call) => call.operation === 'switch'));
});

test('blocked popout, unavailable editor, assistant preview, singleton focus, and unsaved close are explicit', async () => {
  const { coordinator, engine } = setup();
  await coordinator.openEditor({ editorId: 'fixture.two', source: 'menu' });
  const confirmation = await coordinator.openEditor({ editorId: 'fixture.three', source: 'assistant' });
  assert.deepEqual(confirmation, { status: 'confirmation-required', reason: 'assistant-layout-change' });

  const offline = await coordinator.openEditor({ editorId: 'fixture.offline', source: 'menu' });
  assert.equal(offline.status, 'unavailable');
  const denied = await coordinator.openEditor({ editorId: 'fixture.denied', source: 'menu' });
  assert.equal(denied.status, 'unavailable');

  engine.popoutBlocked = true;
  const popout = await coordinator.openEditor({ editorId: 'fixture.three', placement: { mode: 'popout' }, source: 'menu' });
  assert.deepEqual(popout, { status: 'unavailable', code: 'POPOUT_BLOCKED' });

  const singleton = await coordinator.openEditor({ editorId: 'fixture.singleton', source: 'menu' });
  assert.equal(singleton.status, 'opened');
  if (singleton.status !== 'opened') return;
  assert.equal((await coordinator.openEditor({ editorId: 'fixture.singleton', source: 'keyboard' })).status, 'focused');
  coordinator.setDirty(singleton.instance.instanceId, true);
  assert.deepEqual(await coordinator.closeEditor(singleton.instance.instanceId), {
    status: 'confirmation-required', reason: 'unsaved-editor',
  });
  assert.equal((await coordinator.closeEditor(singleton.instance.instanceId, true)).status, 'closed');
});

test('undo restores the prior layout and Judge reset is a single operation', async () => {
  const { coordinator, engine } = setup();
  await coordinator.openEditor({ editorId: 'fixture.two', source: 'menu' });
  assert.equal(Object.keys(coordinator.snapshot().instances).length, 2);
  assert.equal(await coordinator.undo(), true);
  assert.equal(Object.keys(coordinator.snapshot().instances).length, 1);
  assert.equal(await coordinator.undo(), false);

  await coordinator.reset('judge');
  const judge = coordinator.snapshot();
  assert.equal(judge.workspaceId, 'judge');
  assert.equal(Object.keys(judge.instances).length, 4);
  assert.equal(judge.drawers.left.mode, 'peek');
  assert.equal(judge.drawers.bottom.mode, 'peek');
  assert.equal(Object.values(judge.instances).filter((instance) => instance.locked).length, 3);
  assert.equal(engine.calls.filter((call) => call.operation === 'restore').length, 2);
  assert.equal((await coordinator.reset('judge')).status, 'completed');
  assert.equal((await coordinator.reset('home')).status, 'completed');
});

test('same-workspace reset protects dirty editors outside the Judge one-click preset', async () => {
  const { coordinator } = setup();
  const opened = await coordinator.openEditor({ editorId: 'fixture.two', source: 'menu' });
  assert.equal(opened.status, 'opened');
  if (opened.status !== 'opened') return;
  coordinator.setDirty(opened.instance.instanceId, true);
  assert.deepEqual(await coordinator.reset('home'), {
    status: 'confirmation-required', reason: 'unsaved-editor',
  });
  assert.equal((await coordinator.reset('home', { source: 'button', confirmed: true })).status, 'completed');
});

test('join, switch, and maximize mark a preset layout as customized', async () => {
  const switchSetup = setup();
  const switchInstance = Object.values(switchSetup.coordinator.snapshot().instances)[0]!;
  await switchSetup.coordinator.switchEditor(switchInstance.instanceId, 'fixture.two');
  assert.equal(switchSetup.coordinator.isCustomized(), true);

  const maximizeSetup = setup();
  await maximizeSetup.coordinator.toggleMaximize(maximizeSetup.coordinator.snapshot().areas[0]!.areaId);
  assert.equal(maximizeSetup.coordinator.isCustomized(), true);

  const joinSetup = setup();
  await joinSetup.coordinator.reset('design');
  const [target, source] = joinSetup.coordinator.snapshot().areas;
  assert.ok(target && source);
  await joinSetup.coordinator.joinAreas(source!.areaId, target!.areaId);
  assert.equal(joinSetup.coordinator.isCustomized(), true);
});

test('implicit tab placement follows Dockview active panels outside the main grid', async () => {
  const { coordinator, engine } = setup();
  const drawer = await coordinator.openEditor({
    editorId: 'fixture.two', placement: { mode: 'drawer', edge: 'right' }, source: 'menu',
  });
  assert.equal(drawer.status, 'opened');
  if (drawer.status !== 'opened') return;
  engine.topology = {
    groups: [{
      groupId: 'forge-edge-right', location: 'edge', edge: 'right',
      tabs: [drawer.instance.instanceId], activeInstanceId: drawer.instance.instanceId,
      headerPosition: 'top', collapsed: false, peeking: true, autoHide: true,
    }],
    activeInstanceId: drawer.instance.instanceId,
    maximizedInstanceId: null,
  };
  const tab = await coordinator.openEditor({ editorId: 'fixture.three', source: 'menu' });
  assert.equal(tab.status, 'opened');
  if (tab.status !== 'opened') return;
  assert.deepEqual(coordinator.snapshot().drawers.right.tabs, [
    drawer.instance.instanceId,
    tab.instance.instanceId,
  ]);
});

test('targetless move rejects when no non-moving panel exists', async () => {
  const { coordinator } = setup();
  const onlyInstance = Object.values(coordinator.snapshot().instances)[0]!;
  assert.deepEqual(await coordinator.moveEditor(onlyInstance.instanceId, {
    mode: 'split', direction: 'right',
  }), { status: 'rejected', reason: 'invalid-docking-mutation' });
});

test('drawer state and size synchronize into versioned workspace history', async () => {
  const { coordinator } = setup();
  coordinator.syncDrawer({
    edge: 'left',
    mode: 'pinned',
    size: 360,
    lastOpenSize: 360,
    tabs: [],
    activeInstanceId: null,
  });
  assert.equal(coordinator.snapshot().drawers.left.mode, 'pinned');
  assert.equal(coordinator.snapshot().drawers.left.size, 360);
  assert.equal(await coordinator.undo(), true);
  assert.equal(coordinator.snapshot().drawers.left.mode, 'hidden');
  assert.equal(coordinator.snapshot().drawers.left.size, 280);
});

test('lazy-load failure, context pinning, and locked close produce visible typed state', async () => {
  const { coordinator, events } = setup();
  const loadFailures: string[] = [];
  const bindings: string[] = [];
  events.on('workbench.editor.load_failed@1', ({ code }) => loadFailures.push(code));
  events.on('workbench.context.binding_changed@1', ({ binding }) => bindings.push(binding.mode));
  const opened = await coordinator.openEditor({ editorId: 'fixture.load-failure', source: 'menu' });
  assert.equal(opened.status, 'opened');
  if (opened.status !== 'opened') return;
  await coordinator.loadEditor(opened.instance.instanceId);
  assert.equal(coordinator.snapshot().instances[opened.instance.instanceId]?.lifecycle, 'failed');
  assert.deepEqual(loadFailures, ['EDITOR_LOAD_FAILED']);
  coordinator.setContextBinding(opened.instance.instanceId, {
    mode: 'pinned', context: { sceneId: 'scn_pinned' },
  });
  assert.deepEqual(bindings, ['pinned']);

  await coordinator.reset('judge');
  const locked = Object.values(coordinator.snapshot().instances).find((instance) => instance.locked);
  assert.ok(locked);
  assert.deepEqual(await coordinator.closeEditor(locked!.instanceId), {
    status: 'rejected', reason: 'locked-editor',
  });
});

test('replace is atomic, respects locks, and never leaves an orphaned instance', async () => {
  const { coordinator } = setup();
  const target = await coordinator.openEditor({ editorId: 'fixture.two', source: 'menu' });
  assert.equal(target.status, 'opened');
  if (target.status !== 'opened') return;
  const moving = await coordinator.openEditor({ editorId: 'fixture.three', source: 'menu' });
  assert.equal(moving.status, 'opened');
  if (moving.status !== 'opened') return;
  const moved = await coordinator.moveEditor(moving.instance.instanceId, {
    mode: 'replace', relativeToInstanceId: target.instance.instanceId,
  });
  assert.equal(moved.status, 'completed');
  const document = coordinator.snapshot();
  assert.equal(document.instances[target.instance.instanceId], undefined);
  validateWorkspaceDocument(document);

  await coordinator.reset('judge');
  const locked = Object.values(coordinator.snapshot().instances).find((instance) => instance.locked)!;
  assert.deepEqual(await coordinator.openEditor({
    editorId: 'fixture.two',
    placement: { mode: 'replace', relativeToInstanceId: locked.instanceId },
    source: 'button',
  }), { status: 'rejected', reason: 'locked-editor' });
  assert.deepEqual(await coordinator.switchEditor(locked.instanceId, 'fixture.two'), {
    status: 'rejected', reason: 'locked-editor',
  });
});

test('undo restores the recent-close stack and prevents duplicate reopen IDs', async () => {
  const { coordinator } = setup();
  const opened = await coordinator.openEditor({ editorId: 'fixture.two', source: 'menu' });
  assert.equal(opened.status, 'opened');
  if (opened.status !== 'opened') return;
  assert.equal((await coordinator.closeEditor(opened.instance.instanceId)).status, 'closed');
  assert.equal(await coordinator.undo(), true);
  assert.deepEqual(await coordinator.reopenEditor(), { status: 'empty' });
  validateWorkspaceDocument(coordinator.snapshot());
});

test('assistant cannot self-confirm a material mutation on a customized workspace', async () => {
  const { coordinator } = setup();
  await coordinator.openEditor({ editorId: 'fixture.two', source: 'menu' });
  assert.deepEqual(await coordinator.reset('judge', { source: 'assistant', confirmed: true }), {
    status: 'confirmation-required', reason: 'assistant-layout-change',
  });
  assert.notEqual(coordinator.snapshot().workspaceId, 'judge');
});

test('native Dockview mutations reconcile tabs and reject removal of dirty editors', async () => {
  const { coordinator, engine } = setup();
  const opened = await coordinator.openEditor({ editorId: 'fixture.two', source: 'menu' });
  assert.equal(opened.status, 'opened');
  if (opened.status !== 'opened') return;
  const before = coordinator.snapshot();
  engine.topology = {
    groups: [{
      groupId: 'dock-main', location: 'grid', tabs: Object.keys(before.instances),
      activeInstanceId: opened.instance.instanceId, headerPosition: 'top',
    }],
    activeInstanceId: opened.instance.instanceId,
    maximizedInstanceId: null,
  };
  coordinator.beginDockviewMutation('move');
  assert.equal((await coordinator.completeDockviewMutation('move', engine.topology)).status, 'completed');
  validateWorkspaceDocument(coordinator.snapshot());

  coordinator.setDirty(opened.instance.instanceId, true);
  coordinator.beginDockviewMutation('remove');
  engine.topology = {
    ...engine.topology,
    groups: engine.topology.groups.map((group) => ({
      ...group,
      tabs: group.tabs.filter((id) => id !== opened.instance.instanceId),
      activeInstanceId: group.tabs.find((id) => id !== opened.instance.instanceId) ?? null,
    })),
  };
  assert.deepEqual(await coordinator.completeDockviewMutation('remove', engine.topology), {
    status: 'confirmation-required', reason: 'unsaved-editor',
  });
});
