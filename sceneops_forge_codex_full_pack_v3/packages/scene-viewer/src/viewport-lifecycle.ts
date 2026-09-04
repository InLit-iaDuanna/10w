export type ViewportRenderMode = 'suspended' | 'on-demand' | 'continuous';

export interface ViewportPixelSize {
  readonly cssWidth: number;
  readonly cssHeight: number;
  readonly devicePixelRatio: number;
  readonly pixelWidth: number;
  readonly pixelHeight: number;
}

export interface ViewportLifecycleSnapshot {
  readonly viewportId: string;
  readonly visible: boolean;
  readonly active: boolean;
  readonly continuousRequested: boolean;
  readonly renderMode: ViewportRenderMode;
  readonly size: ViewportPixelSize;
}

export interface ViewportRuntimePort {
  resizeViewport(size: ViewportPixelSize): void;
  setRenderMode(mode: ViewportRenderMode): void;
  invalidateFrame(): void;
}

interface ContinuousViewportEntry {
  requested: boolean;
  granted: boolean;
  onGrantChanged(granted: boolean): void;
}

export class ContinuousViewportBudget {
  readonly #maximum: number;
  readonly #entries = new Map<string, ContinuousViewportEntry>();

  constructor(maximum = 2) {
    if (!Number.isInteger(maximum) || maximum < 1) {
      throw new ViewportLifecycleError(
        'INVALID_CONTINUOUS_BUDGET',
        'Continuous viewport budget must be a positive integer.',
      );
    }
    this.#maximum = maximum;
  }

  register(viewportId: string, onGrantChanged: (granted: boolean) => void): () => void {
    assertViewportId(viewportId);
    if (this.#entries.has(viewportId)) {
      throw new ViewportLifecycleError(
        'DUPLICATE_VIEWPORT_ID',
        `Viewport ${viewportId} is already registered with the render budget.`,
      );
    }
    this.#entries.set(viewportId, { requested: false, granted: false, onGrantChanged });
    onGrantChanged(false);
    return () => {
      if (this.#entries.delete(viewportId)) this.#reconcile();
    };
  }

  setRequested(viewportId: string, requested: boolean): void {
    const entry = this.#entries.get(viewportId);
    if (!entry) {
      throw new ViewportLifecycleError(
        'UNKNOWN_VIEWPORT_ID',
        `Viewport ${viewportId} is not registered with the render budget.`,
      );
    }
    if (entry.requested === requested) return;
    entry.requested = requested;
    this.#reconcile();
  }

  grantedViewportIds(): readonly string[] {
    return Object.freeze(
      [...this.#entries]
        .filter(([, entry]) => entry.granted)
        .map(([viewportId]) => viewportId),
    );
  }

  #reconcile(): void {
    let remaining = this.#maximum;
    for (const entry of this.#entries.values()) {
      const nextGranted = entry.requested && remaining > 0;
      if (nextGranted) remaining -= 1;
      if (entry.granted === nextGranted) continue;
      entry.granted = nextGranted;
      entry.onGrantChanged(nextGranted);
    }
  }
}

export class ViewportLifecycleController {
  readonly #viewportId: string;
  readonly #runtime: ViewportRuntimePort;
  #visible = false;
  #active = false;
  #continuousRequested = false;
  #continuousGranted = false;
  #renderMode: ViewportRenderMode = 'suspended';
  #size: ViewportPixelSize = freezeSize(0, 0, 1);
  #disposed = false;
  readonly #budget: ContinuousViewportBudget | undefined;
  readonly #unregisterBudget: (() => void) | undefined;

  constructor(
    viewportId: string,
    runtime: ViewportRuntimePort,
    budget?: ContinuousViewportBudget,
  ) {
    assertViewportId(viewportId);
    this.#viewportId = viewportId;
    this.#runtime = runtime;
    this.#budget = budget;
    this.#unregisterBudget = budget?.register(viewportId, (granted) => {
      this.#continuousGranted = granted;
      this.#applyRenderMode();
    });
    this.#runtime.setRenderMode('suspended');
  }

  resize(cssWidth: number, cssHeight: number, devicePixelRatio: number): ViewportLifecycleSnapshot {
    this.#assertActive();
    assertSize(cssWidth, cssHeight, devicePixelRatio);
    const nextSize = freezeSize(cssWidth, cssHeight, devicePixelRatio);
    const changed = !sameSize(this.#size, nextSize);
    this.#size = nextSize;
    if (changed) this.#runtime.resizeViewport(nextSize);
    this.#reconcileRenderMode();
    return this.snapshot();
  }

  setVisibility(visible: boolean, active: boolean): ViewportLifecycleSnapshot {
    this.#assertActive();
    this.#visible = visible;
    this.#active = active;
    this.#reconcileRenderMode();
    return this.snapshot();
  }

  requestContinuousRendering(requested: boolean): ViewportLifecycleSnapshot {
    this.#assertActive();
    this.#continuousRequested = requested;
    this.#reconcileRenderMode();
    return this.snapshot();
  }

  dispose(): void {
    if (this.#disposed) return;
    this.#visible = false;
    this.#active = false;
    this.#reconcileRenderMode();
    this.#unregisterBudget?.();
    this.#disposed = true;
  }

  invalidate(): boolean {
    this.#assertActive();
    if (this.#renderMode === 'suspended') return false;
    this.#runtime.invalidateFrame();
    return true;
  }

  snapshot(): ViewportLifecycleSnapshot {
    return Object.freeze({
      viewportId: this.#viewportId,
      visible: this.#visible,
      active: this.#active,
      continuousRequested: this.#continuousRequested,
      renderMode: this.#renderMode,
      size: this.#size,
    });
  }

  #reconcileRenderMode(): void {
    const hasArea = this.#size.pixelWidth > 0 && this.#size.pixelHeight > 0;
    const eligible = this.#visible && this.#active && hasArea;
    this.#budget?.setRequested(this.#viewportId, eligible && this.#continuousRequested);
    this.#applyRenderMode();
  }

  #applyRenderMode(): void {
    const hasArea = this.#size.pixelWidth > 0 && this.#size.pixelHeight > 0;
    const nextMode: ViewportRenderMode = !this.#visible || !this.#active || !hasArea
      ? 'suspended'
      : this.#continuousRequested && (this.#budget === undefined || this.#continuousGranted)
        ? 'continuous'
        : 'on-demand';
    if (nextMode === this.#renderMode) return;
    this.#renderMode = nextMode;
    this.#runtime.setRenderMode(nextMode);
  }

  #assertActive(): void {
    if (this.#disposed) {
      throw new ViewportLifecycleError('VIEWPORT_DISPOSED', 'Viewport lifecycle is disposed.');
    }
  }
}

export class ViewportLifecycleError extends Error {
  readonly code:
    | 'INVALID_VIEWPORT_ID'
    | 'INVALID_VIEWPORT_SIZE'
    | 'INVALID_CONTINUOUS_BUDGET'
    | 'DUPLICATE_VIEWPORT_ID'
    | 'UNKNOWN_VIEWPORT_ID'
    | 'VIEWPORT_DISPOSED';

  constructor(
    code: ViewportLifecycleError['code'],
    message: string,
  ) {
    super(message);
    this.name = 'ViewportLifecycleError';
    this.code = code;
  }
}

function assertViewportId(viewportId: string): void {
  if (viewportId.length === 0 || viewportId.trim() !== viewportId) {
    throw new ViewportLifecycleError(
      'INVALID_VIEWPORT_ID',
      'viewportId must be a non-empty, trimmed string.',
    );
  }
}

function assertSize(width: number, height: number, devicePixelRatio: number): void {
  if (
    !Number.isFinite(width)
    || !Number.isFinite(height)
    || !Number.isFinite(devicePixelRatio)
    || width < 0
    || height < 0
    || devicePixelRatio <= 0
  ) {
    throw new ViewportLifecycleError(
      'INVALID_VIEWPORT_SIZE',
      'Viewport size requires finite, non-negative dimensions and a positive pixel ratio.',
    );
  }
}

function freezeSize(
  cssWidth: number,
  cssHeight: number,
  devicePixelRatio: number,
): ViewportPixelSize {
  return Object.freeze({
    cssWidth,
    cssHeight,
    devicePixelRatio,
    pixelWidth: cssWidth === 0 ? 0 : Math.max(1, Math.round(cssWidth * devicePixelRatio)),
    pixelHeight: cssHeight === 0 ? 0 : Math.max(1, Math.round(cssHeight * devicePixelRatio)),
  });
}

function sameSize(left: ViewportPixelSize, right: ViewportPixelSize): boolean {
  return left.cssWidth === right.cssWidth
    && left.cssHeight === right.cssHeight
    && left.devicePixelRatio === right.devicePixelRatio;
}
