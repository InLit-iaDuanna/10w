import type { Edge, EdgeDrawerCoordinator } from '@sceneops/forge-shell';

interface PointerSample {
  pointerId: number;
  clientX: number;
  clientY: number;
}

export class EdgePointerGesture {
  #start: PointerSample | null = null;
  readonly edge: Edge;
  readonly coordinator: EdgeDrawerCoordinator;
  constructor(edge: Edge, coordinator: EdgeDrawerCoordinator) {
    this.edge = edge;
    this.coordinator = coordinator;
  }

  begin(event: PointerSample & { button: number; isPrimary: boolean; shiftKey: boolean; altKey: boolean }): boolean {
    if (!event.isPrimary || event.button !== 0 || this.#start) return false;
    this.#start = { pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY };
    this.coordinator.begin(this.edge, { shiftKey: event.shiftKey, altKey: event.altKey });
    return true;
  }

  move(event: PointerSample) {
    if (!this.#start || event.pointerId !== this.#start.pointerId) return null;
    const distance = this.edge === 'left' || this.edge === 'right'
      ? event.clientX - this.#start.clientX : event.clientY - this.#start.clientY;
    return this.coordinator.move(this.edge === 'right' || this.edge === 'bottom' ? -distance : distance);
  }

  end(event: PointerSample) {
    const start = this.#start;
    if (!this.move(event)) return null;
    this.#start = null;
    // A click is not a zero-length close drag. Let the double-click handler
    // perform its one toggle without two pointer-up mutations first.
    if (start?.clientX === event.clientX && start.clientY === event.clientY) {
      this.coordinator.cancel();
      return null;
    }
    return this.coordinator.end();
  }

  cancel(pointerId: number): boolean {
    if (this.#start?.pointerId !== pointerId) return false;
    this.#start = null;
    this.coordinator.cancel();
    return true;
  }
}
