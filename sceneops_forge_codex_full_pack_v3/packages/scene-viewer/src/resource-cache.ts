export type ResourceCacheEntryState = 'loading' | 'ready';

export interface ResourceCacheEntrySnapshot<TKey> {
  readonly key: TKey;
  readonly state: ResourceCacheEntryState;
  readonly referenceCount: number;
}

export interface ResourceLease<TKey, TValue> {
  readonly key: TKey;
  readonly value: TValue;
  readonly released: boolean;
  release(): void;
}

interface ResourceCacheEntry<TValue> {
  state: ResourceCacheEntryState;
  referenceCount: number;
  value: TValue | undefined;
  promise: Promise<TValue>;
}

export class SharedResourceCache<TKey, TValue> {
  readonly #entries = new Map<TKey, ResourceCacheEntry<TValue>>();
  readonly #disposeResource: (value: TValue, key: TKey) => void;
  #closed = false;

  constructor(disposeResource: (value: TValue, key: TKey) => void) {
    this.#disposeResource = disposeResource;
  }

  async acquire(
    key: TKey,
    loadResource: (key: TKey) => TValue | Promise<TValue>,
  ): Promise<ResourceLease<TKey, TValue>> {
    if (this.#closed) {
      throw new ResourceCacheError('CACHE_CLOSED', 'Cannot acquire from a closed resource cache.');
    }
    let entry = this.#entries.get(key);
    if (!entry) {
      entry = this.#createEntry(key, loadResource);
      this.#entries.set(key, entry);
    }
    entry.referenceCount += 1;

    try {
      const value = await entry.promise;
      return this.#createLease(key, entry, value);
    } catch (error) {
      entry.referenceCount -= 1;
      if (entry.referenceCount === 0 && this.#entries.get(key) === entry) {
        this.#entries.delete(key);
      }
      throw error;
    }
  }

  inspect(): readonly ResourceCacheEntrySnapshot<TKey>[] {
    return Object.freeze([...this.#entries].map(([key, entry]) => Object.freeze({
      key,
      state: entry.state,
      referenceCount: entry.referenceCount,
    })));
  }

  evict(key: TKey): boolean {
    const entry = this.#entries.get(key);
    if (!entry) return false;
    if (entry.referenceCount !== 0) {
      throw new ResourceCacheError(
        'RESOURCE_IN_USE',
        'Cannot evict a resource while a viewport holds a lease.',
      );
    }
    if (entry.state !== 'ready') {
      throw new ResourceCacheError(
        'RESOURCE_LOADING',
        'Cannot evict a resource while it is loading.',
      );
    }
    this.#disposeResource(entry.value as TValue, key);
    this.#entries.delete(key);
    return true;
  }

  evictUnused(): number {
    const unusedKeys = [...this.#entries]
      .filter(([, entry]) => entry.referenceCount === 0 && entry.state === 'ready')
      .map(([key]) => key);
    for (const key of unusedKeys) this.evict(key);
    return unusedKeys.length;
  }

  close(): void {
    const active = [...this.#entries.values()].filter((entry) => entry.referenceCount > 0);
    if (active.length > 0) {
      throw new ResourceCacheError(
        'RESOURCE_IN_USE',
        `Cannot close cache while ${active.length} resource entries are leased.`,
      );
    }
    this.evictUnused();
    this.#closed = true;
  }

  #createEntry(
    key: TKey,
    loadResource: (key: TKey) => TValue | Promise<TValue>,
  ): ResourceCacheEntry<TValue> {
    const entry: ResourceCacheEntry<TValue> = {
      state: 'loading',
      referenceCount: 0,
      value: undefined,
      promise: Promise.resolve(undefined as TValue),
    };
    entry.promise = Promise.resolve()
      .then(() => loadResource(key))
      .then((value) => {
        entry.state = 'ready';
        entry.value = value;
        return value;
      });
    return entry;
  }

  #createLease(
    key: TKey,
    entry: ResourceCacheEntry<TValue>,
    value: TValue,
  ): ResourceLease<TKey, TValue> {
    let released = false;
    return {
      key,
      value,
      get released() {
        return released;
      },
      release: () => {
        if (released) return;
        released = true;
        entry.referenceCount -= 1;
        if (entry.referenceCount < 0) {
          throw new ResourceCacheError(
            'INVALID_REFERENCE_COUNT',
            'Resource reference count became negative.',
          );
        }
      },
    };
  }
}

export class ResourceCacheError extends Error {
  readonly code:
    | 'CACHE_CLOSED'
    | 'RESOURCE_IN_USE'
    | 'RESOURCE_LOADING'
    | 'INVALID_REFERENCE_COUNT';

  constructor(
    code:
      | 'CACHE_CLOSED'
      | 'RESOURCE_IN_USE'
      | 'RESOURCE_LOADING'
      | 'INVALID_REFERENCE_COUNT',
    message: string,
  ) {
    super(message);
    this.name = 'ResourceCacheError';
    this.code = code;
  }
}
