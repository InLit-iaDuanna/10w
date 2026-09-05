import test from 'node:test';
import assert from 'node:assert/strict';
import { EdgeDrawerCoordinator } from '../state/edge-drawer-coordinator.ts';
import { createDefaultDrawers } from '../fixtures/workspace-presets.ts';
import { WorkbenchEventBus } from '../events/workbench-event-bus.ts';

test('all four edges transition deterministically through hidden, peek, and pinned', () => {
  const events = new WorkbenchEventBus();
  const changes: string[] = [];
  events.on('workbench.drawer.changed@1', ({ edge, mode }) => changes.push(`${edge}:${mode}`));
  const coordinator = new EdgeDrawerCoordinator(createDefaultDrawers(), events);

  for (const edge of ['left', 'right', 'top', 'bottom'] as const) {
    coordinator.begin(edge);
    const preview = coordinator.move(79);
    assert.equal(preview.kind, 'none');
    if (preview.kind === 'none') assert.equal(preview.revealLine, true);
    assert.equal(coordinator.end().kind, 'drawer');
    assert.equal(coordinator.get(edge).mode, 'hidden');

    coordinator.begin(edge);
    coordinator.move(120);
    coordinator.end();
    assert.equal(coordinator.get(edge).mode, 'peek');

    coordinator.begin(edge);
    coordinator.move(260);
    coordinator.end();
    assert.equal(coordinator.get(edge).mode, 'pinned');

    coordinator.begin(edge);
    coordinator.move(40);
    coordinator.end();
    assert.equal(coordinator.get(edge).mode, 'hidden');
  }
  assert.equal(changes.length, 12);
});

test('modifier, double-click, keyboard, menu, and Escape alternatives are available', () => {
  const coordinator = new EdgeDrawerCoordinator(createDefaultDrawers(), new WorkbenchEventBus());
  coordinator.begin('left', { shiftKey: true });
  coordinator.move(20);
  coordinator.end();
  assert.equal(coordinator.get('left').mode, 'pinned');

  coordinator.setMode('right', 'peek', 180);
  coordinator.dismissPeek('right');
  assert.equal(coordinator.get('right').mode, 'hidden');

  assert.equal(coordinator.keyboardToggle('top').mode, 'peek');
  assert.equal(coordinator.keyboardToggle('top').mode, 'hidden');
  assert.equal(coordinator.setMode('bottom', 'pinned').mode, 'pinned');
  assert.equal(coordinator.toggleLastSize('bottom').mode, 'hidden');
  assert.equal(coordinator.toggleLastSize('bottom').size, 280);

  coordinator.begin('right', { altKey: true });
  coordinator.move(15);
  assert.deepEqual(coordinator.end(), { kind: 'floating-request', edge: 'right' });
  assert.equal(coordinator.handleVisible(119, false), false);
  assert.equal(coordinator.handleVisible(120, false), true);
  assert.equal(coordinator.handleVisible(0, true), true);
  assert.equal(coordinator.pointerTargetSize(false), 28);
  assert.equal(coordinator.pointerTargetSize(true), 36);
});

test('short revealed drawers retain enough space for the function toolbar and choices', () => {
  const coordinator = new EdgeDrawerCoordinator(createDefaultDrawers(), new WorkbenchEventBus());
  for (const edge of ['left', 'right', 'top', 'bottom'] as const) {
    coordinator.begin(edge);
    coordinator.move(80);
    coordinator.end();
    assert.equal(coordinator.get(edge).mode, 'peek');
    assert.equal(coordinator.get(edge).size, 180);
  }
});
