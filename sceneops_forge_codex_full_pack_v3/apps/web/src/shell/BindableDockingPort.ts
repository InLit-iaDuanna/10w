import type {
  DockingEnginePort,
  DockingTopology,
  EditorInstance,
  EditorPlacement,
  JsonValue,
} from '@sceneops/forge-shell';

/** Breaks the React onReady/coordinator construction cycle without buffering mutations. */
export class BindableDockingPort implements DockingEnginePort {
  #delegate: DockingEnginePort | null = null;

  bind(delegate: DockingEnginePort): void {
    if (this.#delegate) throw new Error('Docking engine is already bound');
    this.#delegate = delegate;
  }

  capture(): JsonValue {
    return this.#requireDelegate().capture();
  }

  describe(): DockingTopology {
    return this.#requireDelegate().describe();
  }

  restore(layout: JsonValue): void | Promise<void> {
    return this.#requireDelegate().restore(layout);
  }

  open(instance: EditorInstance, placement: EditorPlacement): void | boolean | Promise<void | boolean> {
    return this.#requireDelegate().open(instance, placement);
  }

  close(instanceId: string): void | Promise<void> {
    return this.#requireDelegate().close(instanceId);
  }

  move(instance: EditorInstance, placement: EditorPlacement): void | boolean | Promise<void | boolean> {
    return this.#requireDelegate().move(instance, placement);
  }

  switchEditor(instance: EditorInstance): void | Promise<void> {
    return this.#requireDelegate().switchEditor(instance);
  }

  join(sourceInstanceId: string, targetInstanceId: string): void | Promise<void> {
    return this.#requireDelegate().join(sourceInstanceId, targetInstanceId);
  }

  maximize(instanceId: string | null): void | Promise<void> {
    return this.#requireDelegate().maximize(instanceId);
  }

  focus(instanceId: string): void | Promise<void> {
    return this.#requireDelegate().focus(instanceId);
  }

  #requireDelegate(): DockingEnginePort {
    if (!this.#delegate) throw new Error('Docking engine is not ready');
    return this.#delegate;
  }
}
