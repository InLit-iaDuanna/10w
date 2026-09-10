import { flushSync } from 'react-dom';
import type { Edge } from '@sceneops/forge-shell';
import { regionPreviewPath, REGION_REVEAL_DURATION, REGION_REVEAL_EASING, type RegionPlacementOrigin } from './regionPreviewGeometry';

/** Animate live native surfaces from their measured old layout into the new layout. */
export async function animateRegionPlacement(root: HTMLElement, edge: Edge, origin: RegionPlacementOrigin, update: () => Promise<HTMLElement>): Promise<void> {
  const win = root.ownerDocument.defaultView!;
  if (win.matchMedia('(prefers-reduced-motion: reduce)').matches) { await update(); origin.onPrepared?.(); return; }
  const surfaces = () => [...root.querySelectorAll<HTMLElement>('.dv-groupview, .dv-render-overlay')];
  const before = new Map(surfaces().map(element => [element, element.getBoundingClientRect()]));
  const region = await update();
  flushSync(() => {});
  // Dockview positions sibling editor overlays in its queued layout frame.
  // Run after that work, before the browser paints the new positions.
  await new Promise<void>(resolve => win.requestAnimationFrame(() => resolve()));
  const rect = region.getBoundingClientRect();
  const measured = surfaces().map(element => ({ element, next: element.getBoundingClientRect(), previous: before.get(element) }));
  const vertical = edge === 'left' || edge === 'right';
  const depth = vertical ? rect.width : rect.height;
  const center = vertical ? origin.y - rect.top : origin.x - rect.left;
  const animations: Animation[] = [];
  const entering: HTMLElement[] = [];
  const timing = { duration: REGION_REVEAL_DURATION, easing: REGION_REVEAL_EASING, fill: 'both' as const };
  try {
    for (const { element, next, previous } of measured) {
      if (next.width === 0 || next.height === 0) continue;
      if (previous) {
        if (previous.width === 0 || previous.height === 0) continue;
        if (previous.left === next.left && previous.top === next.top) continue;
        animations.push(element.animate([
          { transformOrigin: '0 0', transform: `translate(${previous.left - next.left}px, ${previous.top - next.top}px)` },
          { transformOrigin: '0 0', transform: 'none' },
        ], timing));
      } else {
        element.classList.add('forge-region-entering');
        entering.push(element);
        const curve = (progress: number) => `path('${regionPreviewPath(edge, rect.width, rect.height, center, depth, origin.shoulder, progress, rect.left - next.left, rect.top - next.top)}')`;
        animations.push(element.animate([{ clipPath: curve(0) }, { clipPath: curve(1) }], timing));
      }
    }
    // Both surfaces use the click's original clock: preparation never restarts the curve.
    if (origin.startedAt !== undefined) animations.forEach(animation => { animation.startTime = origin.startedAt!; });
    // Install every first frame before retiring the still-visible drag preview.
    origin.onPrepared?.();
    await Promise.all(animations.map(animation => animation.finished));
  } finally {
    animations.forEach(animation => animation.cancel());
    entering.forEach(element => element.classList.remove('forge-region-entering'));
  }
}
