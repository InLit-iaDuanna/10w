import React, { useRef, useState } from 'react';
import type { Edge, EdgeDrawerCoordinator } from '@sceneops/forge-shell';

export interface EdgeDrawerControllerProps {
  coordinator: EdgeDrawerCoordinator;
  judgeMode: boolean;
  onFloatingRequest(edge: Edge): void;
  onChanged(edge: Edge): void;
}

export function EdgeDrawerController(props: EdgeDrawerControllerProps): React.ReactElement {
  return (
    <>
      {EDGES.map((edge) => (
        <EdgeHandle key={edge} edge={edge} {...props} />
      ))}
    </>
  );
}

function EdgeHandle({
  edge,
  coordinator,
  judgeMode,
  onFloatingRequest,
  onChanged,
}: EdgeDrawerControllerProps & { edge: Edge }): React.ReactElement {
  const pointerStart = useRef<number | null>(null);
  const [previewSize, setPreviewSize] = useState(0);
  const drawer = coordinator.get(edge);
  const vertical = edge === 'left' || edge === 'right';
  return (
    <button
      type="button"
      className={`forge-edge-handle forge-edge-${edge} is-${drawer.mode}`}
      aria-label={`${EDGE_LABELS[edge]}工具抽屉：${drawer.mode}`}
      data-judge-visible={judgeMode || undefined}
      onDoubleClick={() => { coordinator.toggleLastSize(edge); onChanged(edge); }}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          coordinator.dismissPeek(edge);
        } else if (event.key === 'Enter' || event.key === ' ') {
          coordinator.keyboardToggle(edge, event.shiftKey);
        } else {
          return;
        }
        event.preventDefault();
        onChanged(edge);
      }}
      onPointerDown={(event) => {
        pointerStart.current = vertical ? event.clientX : event.clientY;
        coordinator.begin(edge, { shiftKey: event.shiftKey, altKey: event.altKey });
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={(event) => {
        if (pointerStart.current === null) return;
        const preview = coordinator.move(openDistance(
          edge,
          pointerStart.current,
          vertical ? event.clientX : event.clientY,
        ));
        if (preview.kind === 'none') setPreviewSize(preview.previewSize);
      }}
      onPointerUp={() => {
        if (pointerStart.current === null) return;
        const result = coordinator.end();
        pointerStart.current = null;
        setPreviewSize(0);
        if (result.kind === 'floating-request') onFloatingRequest(edge);
        onChanged(edge);
      }}
      onPointerCancel={() => {
        coordinator.cancel();
        pointerStart.current = null;
        setPreviewSize(0);
      }}
    >
      <span className="forge-edge-handle-label">{judgeMode ? EDGE_LABELS[edge] : '⋮'}</span>
      {previewSize > 0 ? (
        <span
          aria-hidden="true"
          className={`forge-edge-preview forge-edge-preview-${edge}`}
          style={vertical ? { width: previewSize } : { height: previewSize }}
        />
      ) : null}
    </button>
  );
}

function openDistance(edge: Edge, start: number, current: number): number {
  return edge === 'right' || edge === 'bottom' ? start - current : current - start;
}

const EDGES: Edge[] = ['left', 'right', 'top', 'bottom'];
const EDGE_LABELS: Record<Edge, string> = { left: '左侧', right: '右侧', top: '顶部', bottom: '底部' };
