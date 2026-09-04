import type { KeyValueStorage } from "../conversation/repository.ts";

export class MemoryStorage implements KeyValueStorage {
  readonly #values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.#values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.#values.set(key, value);
  }

  removeItem(key: string): void {
    this.#values.delete(key);
  }

  entries(): Array<[string, string]> {
    return [...this.#values.entries()];
  }
}
