import test from 'node:test';
import assert from 'node:assert/strict';
import { EdgePointerGesture } from '../EdgePointerGesture.ts';
import { EdgeDrawerCoordinator } from '../../../../../modules/forge-shell/frontend/src/state/edge-drawer-coordinator.ts';
import { createDefaultDrawers } from '../../../../../modules/forge-shell/frontend/src/fixtures/workspace-presets.ts';
import { WorkbenchEventBus } from '../../../../../modules/forge-shell/frontend/src/events/workbench-event-bus.ts';

const start = { pointerId: 1, clientX: 500, clientY: 500, button: 0, isPrimary: true, shiftKey: false, altKey: false };

for (const edge of ['left', 'right', 'top', 'bottom'] as const) {
  test(`${edge} uses signed inward motion and the final pointer-up position`, () => {
    const coordinator = new EdgeDrawerCoordinator(createDefaultDrawers(), new WorkbenchEventBus());
    const gesture = new EdgePointerGesture(edge, coordinator);
    gesture.begin(start);
    const horizontal = edge === 'left' || edge === 'right';
    const delta = edge === 'right' || edge === 'bottom' ? -300 : 300;
    gesture.end({ ...start, clientX: start.clientX + (horizontal ? delta : 0), clientY: start.clientY + (horizontal ? 0 : delta) });
    assert.equal(coordinator.get(edge).mode, 'pinned');
    assert.equal(coordinator.get(edge).size, 300);
    gesture.begin(start);
    gesture.end(start);
    assert.equal(coordinator.get(edge).mode, 'pinned', 'a click must not act as a close drag');
    gesture.begin(start);
    gesture.end(start);
    coordinator.toggleLastSize(edge);
    assert.equal(coordinator.get(edge).mode, 'hidden');
    coordinator.toggleLastSize(edge);
    gesture.begin(start);
    const closeDelta = edge === 'right' || edge === 'bottom' ? -40 : 40;
    gesture.end({ ...start, clientX: start.clientX + (horizontal ? closeDelta : 0), clientY: start.clientY + (horizontal ? 0 : closeDelta) });
    assert.equal(coordinator.get(edge).mode, 'hidden', 'an actual reverse/short drag still closes');
  });
}

test('cancel or lost capture discards preview and a later pointer-up cannot commit', () => {
  const coordinator = new EdgeDrawerCoordinator(createDefaultDrawers(), new WorkbenchEventBus());
  const gesture = new EdgePointerGesture('left', coordinator);
  for (const reason of ['pointercancel', 'lostpointercapture']) {
    assert.equal(gesture.begin(start), true, reason);
    gesture.move({ ...start, clientX: 900 });
    assert.equal(gesture.cancel(2), false);
    assert.equal(gesture.cancel(1), true);
    assert.equal(gesture.end({ ...start, clientX: 900 }), null);
    assert.equal(coordinator.get('left').mode, 'hidden');
  }
});

test('secondary pointers and mouse buttons do not start or hijack an edge gesture', () => {
  const coordinator = new EdgeDrawerCoordinator(createDefaultDrawers(), new WorkbenchEventBus());
  const gesture = new EdgePointerGesture('left', coordinator);
  assert.equal(gesture.begin({ ...start, button: 2 }), false);
  assert.equal(gesture.begin({ ...start, isPrimary: false }), false);
  assert.equal(gesture.begin(start), true);
  assert.equal(gesture.begin({ ...start, pointerId: 2 }), false);
  assert.equal(gesture.move({ ...start, pointerId: 2 }), null);
  assert.equal(gesture.end({ ...start, pointerId: 2 }), null);
  gesture.end({ ...start, clientX: 620 });
  assert.equal(coordinator.get('left').mode, 'peek');
});
