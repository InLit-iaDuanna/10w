import type { DrawerMode, DrawerState, Edge } from '../contracts.ts';
import type { WorkbenchEventBus } from '../events/workbench-event-bus.ts';

export interface EdgeThresholds {
  reveal: number;
  peek: number;
  pin: number;
  hide: number;
  minSize: number;
  maxSize: number;
  defaultSize: number;
}

export const DEFAULT_EDGE_THRESHOLDS: EdgeThresholds = {
  reveal: 12,
  peek: 80,
  pin: 220,
  hide: 48,
  minSize: 180,
  maxSize: Number.POSITIVE_INFINITY,
  defaultSize: 280,
};

export interface EdgeGestureModifiers {
  shiftKey?: boolean;
  altKey?: boolean;
}

export type EdgeGestureResult =
  | { kind: 'none'; revealLine: boolean; previewSize: number }
  | { kind: 'drawer'; drawer: DrawerState }
  | { kind: 'floating-request'; edge: Edge };

interface ActiveGesture {
  edge: Edge;
  distance: number;
  modifiers: EdgeGestureModifiers;
  startedMode: DrawerMode;
}

export class EdgeDrawerCoordinator {
  readonly #drawers: Record<Edge, DrawerState>;
  readonly #events: WorkbenchEventBus;
  readonly #thresholds: EdgeThresholds;
  #gesture: ActiveGesture | null = null;

  constructor(
    drawers: Record<Edge, DrawerState>,
    events: WorkbenchEventBus,
    thresholds: EdgeThresholds = DEFAULT_EDGE_THRESHOLDS,
  ) {
    this.#drawers = drawers;
    this.#events = events;
    this.#thresholds = thresholds;
  }

  get(edge: Edge): DrawerState {
    return structuredClone(this.#drawers[edge]);
  }

  sync(drawer: DrawerState): void {
    this.#drawers[drawer.edge] = structuredClone(drawer);
  }

  begin(edge: Edge, modifiers: EdgeGestureModifiers = {}): void {
    this.#gesture = { edge, distance: 0, modifiers, startedMode: this.#drawers[edge].mode };
  }

  move(distanceFromEdge: number): EdgeGestureResult {
    if (!this.#gesture) throw new Error('No active edge gesture');
    this.#gesture.distance = Math.max(0, distanceFromEdge);
    return {
      kind: 'none',
      revealLine: this.#gesture.distance >= this.#thresholds.reveal,
      previewSize: clamp(this.#gesture.distance, 0, this.#thresholds.maxSize),
    };
  }

  end(): EdgeGestureResult {
    if (!this.#gesture) throw new Error('No active edge gesture');
    const gesture = this.#gesture;
    this.#gesture = null;
    if (gesture.modifiers.altKey && gesture.distance >= this.#thresholds.reveal) {
      return { kind: 'floating-request', edge: gesture.edge };
    }
    if (gesture.startedMode !== 'hidden' && gesture.distance < this.#thresholds.hide) {
      return { kind: 'drawer', drawer: this.setMode(gesture.edge, 'hidden') };
    }
    if (gesture.modifiers.shiftKey && gesture.distance >= this.#thresholds.reveal) {
      return { kind: 'drawer', drawer: this.setMode(gesture.edge, 'pinned', gesture.distance) };
    }
    if (gesture.distance >= this.#thresholds.pin) {
      return { kind: 'drawer', drawer: this.setMode(gesture.edge, 'pinned', gesture.distance) };
    }
    if (gesture.distance >= this.#thresholds.peek) {
      return { kind: 'drawer', drawer: this.setMode(gesture.edge, 'pinned', gesture.distance) };
    }
    return { kind: 'drawer', drawer: this.setMode(gesture.edge, 'hidden') };
  }

  cancel(): void {
    this.#gesture = null;
  }

  setMode(edge: Edge, mode: DrawerMode, size?: number): DrawerState {
    const drawer = this.#drawers[edge];
    const nextSize = mode === 'hidden' ? drawer.size : this.#normalizeSize(size ?? drawer.lastOpenSize);
    const changed = drawer.mode !== mode || drawer.size !== nextSize;
    drawer.mode = mode;
    drawer.size = nextSize;
    if (mode !== 'hidden') drawer.lastOpenSize = nextSize;
    if (changed) this.#emit(drawer);
    return structuredClone(drawer);
  }

  resize(edge: Edge, size: number): DrawerState {
    const drawer = this.#drawers[edge];
    const nextSize = this.#normalizeSize(size);
    const changed = drawer.size !== nextSize;
    drawer.size = nextSize;
    drawer.lastOpenSize = nextSize;
    if (changed) this.#emit(drawer);
    return structuredClone(drawer);
  }

  toggleLastSize(edge: Edge): DrawerState {
    const drawer = this.#drawers[edge];
    return drawer.mode === 'hidden'
      ? this.setMode(edge, 'pinned', drawer.lastOpenSize)
      : this.setMode(edge, 'hidden');
  }

  dismissPeek(edge?: Edge): void {
    const edges: Edge[] = edge ? [edge] : ['left', 'right', 'top', 'bottom'];
    for (const candidate of edges) {
      if (this.#drawers[candidate].mode === 'peek') this.setMode(candidate, 'hidden');
    }
  }

  keyboardToggle(edge: Edge, pinned = false): DrawerState {
    const drawer = this.#drawers[edge];
    if (drawer.mode !== 'hidden') return this.setMode(edge, 'hidden');
    return this.setMode(edge, pinned ? 'pinned' : 'peek');
  }

  handleVisible(hoverMilliseconds: number, judgeMode: boolean): boolean {
    return judgeMode || hoverMilliseconds >= 120;
  }

  pointerTargetSize(judgeMode: boolean): number {
    return judgeMode ? 36 : 28;
  }

  #normalizeSize(size: number): number {
    return clamp(size || this.#thresholds.defaultSize, this.#thresholds.minSize, this.#thresholds.maxSize);
  }

  #emit(drawer: DrawerState): void {
    this.#events.emit('workbench.drawer.changed@1', {
      edge: drawer.edge,
      mode: drawer.mode,
      size: drawer.size,
    });
  }
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}
