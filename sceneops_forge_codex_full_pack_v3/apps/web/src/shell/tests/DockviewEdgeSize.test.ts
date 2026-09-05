import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

// Exercise the installed engine's actual edge view with a minimal DOM surface.
// EdgeGroupView is package-private; loading its class keeps this test independent
// of browser rendering while executing the patched subscription and disposal.
const require = createRequire(import.meta.url);
const dockviewRequire = createRequire(createRequire(require.resolve('dockview-react')).resolve('dockview'));
const source = readFileSync(dockviewRequire.resolve('dockview-core'), 'utf8');
const edgeSource = source.slice(source.indexOf('var EdgeGroupView = class {'), source.indexOf('var CenterView = class {'));
class Emitter {
  listeners = new Set<(event: unknown) => void>();
  event = (listener: (event: unknown) => void) => {
    this.listeners.add(listener);
    return { dispose: () => this.listeners.delete(listener) };
  };
  fire(event: unknown) { for (const listener of this.listeners) listener(event); }
  dispose() { this.listeners.clear(); }
}
class CompositeDisposable {
  items: Array<{ dispose(): void }> = [];
  addDisposables(...items: Array<{ dispose(): void }>) { this.items.push(...items); }
  dispose() { this.items.forEach(item => item.dispose()); }
}
const EdgeGroupView = runInNewContext(`${edgeSource}\nEdgeGroupView`, { Emitter, CompositeDisposable });

for (const [edge, orientation, axis] of [
  ['left', 'horizontal', 'width'], ['right', 'horizontal', 'width'],
  ['top', 'vertical', 'height'], ['bottom', 'vertical', 'height'],
] as const) {
  test(`installed Dockview ${edge} setSize updates collapsed memory and expanded layout`, () => {
    const sizeEvents = new Emitter();
    const group = {
      element: { classList: { add() {}, toggle() {} }, dataset: {}, querySelector: () => null },
      api: { onDidSizeChange: sizeEvents.event },
    };
    const view = new EdgeGroupView({ id: edge, collapsed: true, initialSize: 200, minimumSize: 80, maximumSize: 640, collapsedSize: 12 }, group, orientation);
    const layouts: Array<{ size: number }> = [];
    view.onDidChange((event: { size: number }) => layouts.push(event));
    sizeEvents.fire({ [axis]: 320 });
    assert.equal(view.lastExpandedSize, 320, 'peek size is read from expanded memory');
    assert.equal(layouts.length, 0, 'collapsed strip must not consume expanded space');
    sizeEvents.fire({ [axis === 'width' ? 'height' : 'width']: 450 });
    assert.equal(view.lastExpandedSize, 320, 'orthogonal dimensions do not resize the edge');
    view.setCollapsed(false);
    sizeEvents.fire({ [axis]: 410 });
    assert.equal(layouts.at(-1)?.size, 410);
    sizeEvents.fire({ [axis]: -100 });
    assert.equal(layouts.at(-1)?.size, 80);
    sizeEvents.fire({ [axis]: 1000 });
    assert.equal(layouts.at(-1)?.size, 640);
    sizeEvents.fire({ [axis]: Number.NaN });
    assert.equal(view.lastExpandedSize, 640);
    view.dispose();
    assert.equal(sizeEvents.listeners.size, 0);
  });
}
