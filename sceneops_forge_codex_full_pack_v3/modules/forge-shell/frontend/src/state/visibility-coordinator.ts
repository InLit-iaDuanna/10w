import type { EditorDefinition } from '../contracts.ts';
import type { WorkbenchEventBus } from '../events/workbench-event-bus.ts';

export class VisibilityCoordinator {
  readonly #visible = new Map<string, boolean>();
  readonly #events: WorkbenchEventBus;

  constructor(events: WorkbenchEventBus) {
    this.#events = events;
  }

  update(instanceId: string, definition: EditorDefinition, visible: boolean): void {
    const previous = this.#visible.get(instanceId);
    if (previous === visible) return;
    this.#visible.set(instanceId, visible);
    this.#events.emit('workbench.visibility.changed@1', {
      instanceId,
      visible,
      suspended: !visible && definition.renderPolicy === 'suspend-when-hidden',
    });
  }

  forget(instanceId: string): void {
    this.#visible.delete(instanceId);
  }
}
