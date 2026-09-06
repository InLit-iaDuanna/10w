import { useRef, useState } from 'react';
import type { Edge } from '@sceneops/forge-shell';
import { recordUiEvent } from '../debug';

export type RegionSplitRequest = (instanceId: string, edge: Edge, size?: number) => Promise<void>;
export type RegionCollapseRequest = (instanceId: string, edge: Edge, crossRatio: number) => Promise<void>;

/** The owning panel is the split target. Dockview, not this gesture, lays out its children. */
export function RegionPullHandles({ instanceId, split, collapse, getBounds }: {
  instanceId: string;
  split: RegionSplitRequest;
  collapse: RegionCollapseRequest;
  getBounds(): DOMRect;
}) {
  return <>{(['top', 'bottom', 'left', 'right'] as const).map(edge =>
    <RegionPullHandle key={edge} instanceId={instanceId} edge={edge} split={split} collapse={collapse} getBounds={getBounds} />)}</>;
}

function RegionPullHandle({ instanceId, edge, split, collapse, getBounds }: {
  instanceId: string;
  edge: Edge;
  split: RegionSplitRequest;
  collapse: RegionCollapseRequest;
  getBounds(): DOMRect;
}) {
  const drag = useRef<{ pointerId: number; origin: number; extent: number; start: number; crossRatio: number } | null>(null);
  const [preview, setPreview] = useState(0);
  const [collapseReady, setCollapseReady] = useState(false);
  const horizontal = edge === 'left' || edge === 'right';
  const inward = edge === 'right' || edge === 'bottom' ? -1 : 1;
  const coordinate = (event: { clientX: number; clientY: number }) => horizontal ? event.clientX : event.clientY;
  const finish = () => { drag.current = null; setPreview(0); setCollapseReady(false); };
  const request = (size?: number) => { void split(instanceId, edge, size); };
  return <button type="button" className={`forge-edge-handle forge-region-pull forge-edge-${edge}`}
    aria-label={`在当前区域${LABELS[edge]}拉出功能`} title="向内拖动拆分当前区域；向相邻区域反向拖动可收起；双击或回车均分"
    data-region-instance={instanceId}
    data-collapse-ready={collapseReady || undefined}
    onDoubleClick={() => request()}
    onKeyDown={event => {
      if (event.key === 'Escape') { finish(); return; }
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); request(); }
    }}
    onPointerDown={event => {
      if (event.button !== 0 || !event.isPrimary || drag.current) return;
      const bounds = getBounds();
      drag.current = { pointerId: event.pointerId, start: coordinate(event), extent: horizontal ? bounds.width : bounds.height,
        origin: edge === 'left' ? bounds.left : edge === 'right' ? bounds.right : edge === 'top' ? bounds.top : bounds.bottom,
        crossRatio: horizontal
          ? Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height))
          : Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)) };
      event.currentTarget.setPointerCapture(event.pointerId);
      recordUiEvent('edge-drag.begin', { edge, instanceId, phase: 'start' });
    }}
    onPointerMove={event => {
      const current = drag.current;
      if (current?.pointerId !== event.pointerId) return;
      const travel = inward * (coordinate(event) - current.start);
      setCollapseReady(travel <= -REGION_COLLAPSE_DRAG_THRESHOLD);
      setPreview(travel <= 0 || Math.abs(coordinate(event) - current.start) < REGION_DRAG_THRESHOLD
        ? 0
        : Math.max(0, Math.min(current.extent, inward * (coordinate(event) - current.origin))));
    }}
    onPointerUp={event => {
      const current = drag.current;
      if (current?.pointerId !== event.pointerId) return;
      const travel = inward * (coordinate(event) - current.start);
      const size = Math.abs(coordinate(event) - current.start) < REGION_DRAG_THRESHOLD || travel <= 0
        ? 0
        : Math.max(0, Math.min(current.extent, inward * (coordinate(event) - current.origin)));
      const shouldCollapse = travel <= -REGION_COLLAPSE_DRAG_THRESHOLD;
      finish();
      event.currentTarget.releasePointerCapture(event.pointerId);
      recordUiEvent('edge-drag.end', { edge, instanceId, size, phase: shouldCollapse || size >= 24 ? 'commit' : 'cancel' });
      if (shouldCollapse) void collapse(instanceId, edge, current.crossRatio);
      else if (size >= 24) request(size);
    }}
    onPointerCancel={finish} onLostPointerCapture={finish}>
    <span className="forge-edge-handle-label">⋮</span>
    {preview >= 24 && <span className={`forge-edge-preview forge-edge-preview-${edge}`} aria-hidden="true"
      style={horizontal ? { width: preview } : { height: preview }} />}
  </button>;
}

const LABELS: Record<Edge, string> = { top: '上方', bottom: '下方', left: '左侧', right: '右侧' };
const REGION_DRAG_THRESHOLD = 12;
const REGION_COLLAPSE_DRAG_THRESHOLD = 48;
