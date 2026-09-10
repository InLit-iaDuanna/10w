import type { Edge } from '@sceneops/forge-shell';

export interface RegionPlacementOrigin { x: number; y: number; shoulder: number; startedAt?: number; onPrepared?(): void }

/** Identical curve commands let the preview become the actual region's reveal mask. */
export function regionPreviewPath(edge: Edge, width: number, height: number, center: number, depth: number, shoulder: number, progress = 0, offsetX = 0, offsetY = 0): string {
  const span = edge === 'left' || edge === 'right' ? height : width;
  center = Math.max(0, Math.min(span, center));
  const mix = (from: number, to: number) => from + (to - from) * progress;
  const flatBefore = Math.min(center, 48), flatAfter = Math.min(span - center, 48);
  const before = Math.min(center - flatBefore, shoulder), after = Math.min(span - center - flatAfter, shoulder);
  const start = center - flatBefore, end = center + flatAfter;
  const xy = (cross: number, inward: number) => {
    if (edge === 'left') return `${inward + offsetX},${cross + offsetY}`;
    if (edge === 'right') return `${width - inward + offsetX},${cross + offsetY}`;
    if (edge === 'top') return `${cross + offsetX},${inward + offsetY}`;
    return `${cross + offsetX},${height - inward + offsetY}`;
  };
  return `M${xy(mix(start - before, 0), 0)} C${xy(mix(start - before * .35, 0), 0)} ${xy(mix(start - before * .65, 0), depth)} ${xy(mix(start, 0), depth)} L${xy(center, depth)} L${xy(mix(end, span), depth)} C${xy(mix(end + after * .65, span), depth)} ${xy(mix(end + after * .35, span), 0)} ${xy(mix(end + after, span), 0)} Z`;
}

export const REGION_REVEAL_DURATION = 320;
export const REGION_REVEAL_EASING = 'cubic-bezier(.32,0,.22,1)';

/** Evaluate the same cubic timing curve used by the native content animation. */
export function regionRevealProgress(elapsed: number): number {
  const x = Math.max(0, Math.min(1, elapsed / REGION_REVEAL_DURATION));
  if (x === 0 || x === 1) return x;
  let low = 0, high = 1;
  for (let i = 0; i < 18; i++) {
    const t = (low + high) / 2, inverse = 1 - t;
    const sample = 3 * inverse * inverse * t * .32 + 3 * inverse * t * t * .22 + t * t * t;
    if (sample < x) low = t; else high = t;
  }
  const t = (low + high) / 2;
  return 3 * (1 - t) * t * t + t * t * t;
}
