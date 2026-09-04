export type SceneOverlayLayer = 'geometry' | 'screen-space' | 'metadata';

export interface SceneOverlayDefinition<TContext, TPayload> {
  readonly id: string;
  readonly label: string;
  readonly layer: SceneOverlayLayer;
  readonly order: number;
  isAvailable(context: TContext): boolean;
  createPayload(context: TContext): TPayload;
}

export interface ResolvedSceneOverlay<TPayload> {
  readonly id: string;
  readonly label: string;
  readonly layer: SceneOverlayLayer;
  readonly payload: TPayload;
}

export interface SceneOverlayAvailability {
  readonly id: string;
  readonly label: string;
  readonly layer: SceneOverlayLayer;
  readonly available: boolean;
}

export class SceneOverlayRegistry<TContext, TPayload> {
  readonly #definitions = new Map<string, SceneOverlayDefinition<TContext, TPayload>>();

  register(definition: SceneOverlayDefinition<TContext, TPayload>): () => void {
    assertDefinition(definition);
    if (this.#definitions.has(definition.id)) {
      throw new SceneOverlayError(
        'DUPLICATE_OVERLAY',
        `Overlay ${definition.id} is already registered.`,
      );
    }
    this.#definitions.set(definition.id, definition);
    return () => {
      if (this.#definitions.get(definition.id) === definition) {
        this.#definitions.delete(definition.id);
      }
    };
  }

  unregister(id: string): boolean {
    return this.#definitions.delete(id);
  }

  list(context: TContext): readonly SceneOverlayAvailability[] {
    return Object.freeze(
      this.#sorted().map((definition) => Object.freeze({
        id: definition.id,
        label: definition.label,
        layer: definition.layer,
        available: definition.isAvailable(context),
      })),
    );
  }

  resolve(id: string, context: TContext): ResolvedSceneOverlay<TPayload> {
    const definition = this.#definitions.get(id);
    if (!definition) {
      throw new SceneOverlayError('UNKNOWN_OVERLAY', `Unknown overlay: ${id}`);
    }
    if (!definition.isAvailable(context)) {
      throw new SceneOverlayError(
        'OVERLAY_UNAVAILABLE',
        `Overlay ${id} is unavailable for the current context.`,
      );
    }
    return Object.freeze({
      id: definition.id,
      label: definition.label,
      layer: definition.layer,
      payload: definition.createPayload(context),
    });
  }

  #sorted(): readonly SceneOverlayDefinition<TContext, TPayload>[] {
    return [...this.#definitions.values()].sort(
      (left, right) => left.order - right.order || left.id.localeCompare(right.id),
    );
  }
}

export class SceneOverlayError extends Error {
  readonly code: 'INVALID_OVERLAY' | 'DUPLICATE_OVERLAY' | 'UNKNOWN_OVERLAY' | 'OVERLAY_UNAVAILABLE';

  constructor(
    code: 'INVALID_OVERLAY' | 'DUPLICATE_OVERLAY' | 'UNKNOWN_OVERLAY' | 'OVERLAY_UNAVAILABLE',
    message: string,
  ) {
    super(message);
    this.name = 'SceneOverlayError';
    this.code = code;
  }
}

function assertDefinition<TContext, TPayload>(
  definition: SceneOverlayDefinition<TContext, TPayload>,
): void {
  if (
    definition.id.length === 0
    || definition.id.trim() !== definition.id
    || definition.label.trim().length === 0
    || !Number.isFinite(definition.order)
  ) {
    throw new SceneOverlayError(
      'INVALID_OVERLAY',
      'Overlay requires a trimmed ID, non-blank label, and finite order.',
    );
  }
}
