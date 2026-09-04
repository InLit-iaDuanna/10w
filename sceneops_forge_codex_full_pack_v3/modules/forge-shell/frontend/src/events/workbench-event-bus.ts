import type { ShellEventMap, ShellEventName } from '../contracts.ts';

type Listener<Name extends ShellEventName> = (payload: ShellEventMap[Name]) => void;

export class WorkbenchEventBus {
  readonly #listeners = new Map<ShellEventName, Set<(payload: never) => void>>();

  on<Name extends ShellEventName>(name: Name, listener: Listener<Name>): () => void {
    const listeners = this.#listeners.get(name) ?? new Set();
    listeners.add(listener as (payload: never) => void);
    this.#listeners.set(name, listeners);
    return () => listeners.delete(listener as (payload: never) => void);
  }

  emit<Name extends ShellEventName>(name: Name, payload: ShellEventMap[Name]): void {
    for (const listener of this.#listeners.get(name) ?? []) listener(payload as never);
  }
}
