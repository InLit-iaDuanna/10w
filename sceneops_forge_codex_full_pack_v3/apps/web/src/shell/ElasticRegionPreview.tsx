import { useEffect, useRef } from 'react';
import { regionPreviewPath, regionRevealProgress } from './regionPreviewGeometry';
import type { Edge } from '@sceneops/forge-shell';

/** The crest stays under the pointer; soft shoulders ease back into the edge. */
export function ElasticRegionPreview({ edge, bounds, point, size, onShoulderChange, frozen = false, expandingSince }: {
  edge: Edge; bounds: DOMRect; point: { x: number; y: number }; size: number;
  frozen?: boolean;
  expandingSince?: number;
  onShoulderChange?(width: number): void;
}) {
  const path = useRef<SVGPathElement>(null);
  const target = useRef({ point, size, bounds, onShoulderChange, frozen, expandingSince });
  target.current = { point, size, bounds, onShoulderChange, frozen, expandingSince };
  useEffect(() => {
    const win = path.current!.ownerDocument.defaultView!;
    const reduced = win.matchMedia('(prefers-reduced-motion: reduce)');
    const vertical = edge === 'left' || edge === 'right';
    let width = 90, velocity = 0, previous = 0, frame = 0;
    const draw = (time: number) => {
      const { bounds: rect, point: cursor, size: depth } = target.current;
      const span = vertical ? rect.height : rect.width;
      const center = vertical ? cursor.y - rect.top : cursor.x - rect.left;
      const wantedWidth = Math.min(span, 110 + Math.sqrt(depth) * 13);
      const dt = previous ? Math.min((time - previous) / 1000, 1 / 30) : 1 / 60;
      previous = time;
      // Damped spring integrated in small steps, independent of display refresh rate.
      for (let step = 0; !target.current.frozen && step < 4; step++) {
        velocity += ((wantedWidth - width) * 180 - velocity * 30) * dt / 4;
        width += velocity * dt / 4;
      }
      if (reduced.matches) { width = wantedWidth; velocity = 0; }
      target.current.onShoulderChange?.(width);
      path.current!.setAttribute('d', regionPreviewPath(edge, rect.width, rect.height, center, depth, width, target.current.expandingSince === undefined ? 0 : reduced.matches ? 1 : regionRevealProgress(time - target.current.expandingSince)));
      frame = win.requestAnimationFrame(draw);
    };
    frame = win.requestAnimationFrame(draw);
    return () => win.cancelAnimationFrame(frame);
  }, [edge]);
  return <svg className={`forge-hover-split-preview forge-elastic-${edge}`} aria-hidden="true"
    style={{ left: bounds.left, top: bounds.top, width: bounds.width, height: bounds.height }}
    viewBox={`0 0 ${bounds.width} ${bounds.height}`}>
    <path ref={path} />
  </svg>;
}
