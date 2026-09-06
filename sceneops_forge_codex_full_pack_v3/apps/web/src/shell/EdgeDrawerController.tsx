import React, { useMemo, useState } from 'react';
import type { Edge, EdgeDrawerCoordinator } from '@sceneops/forge-shell';
import { EdgePointerGesture } from './EdgePointerGesture';
import { recordUiEvent } from '../debug';

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
  const gesture = useMemo(() => new EdgePointerGesture(edge, coordinator), [edge, coordinator]);
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
        const bounds = event.currentTarget.getBoundingClientRect();
        const origin = edge === 'left' ? bounds.left : edge === 'right' ? bounds.right : edge === 'top' ? bounds.top : bounds.bottom;
        if (!gesture.begin(event, origin)) return;
        recordUiEvent('edge-drag.begin', { edge, phase: 'start', size: drawer.size, mode: drawer.mode });
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={(event) => {
        const preview = gesture.move(event);
        if (preview?.kind === 'none') setPreviewSize(preview.previewSize);
      }}
      onPointerUp={(event) => {
        if (!gesture.active) return;
        const result = gesture.end(event);
        recordUiEvent('edge-drag.end', { edge, phase: result ? 'commit' : 'cancel', size: coordinator.get(edge).size, mode: coordinator.get(edge).mode });
        if (!result) return;
        setPreviewSize(0);
        event.currentTarget.releasePointerCapture(event.pointerId);
        if (result.kind === 'floating-request') onFloatingRequest(edge);
        onChanged(edge);
      }}
      onPointerCancel={(event) => {
        if (gesture.cancel(event.pointerId)) {
          setPreviewSize(0);
          recordUiEvent('edge-drag.end', { edge, phase: 'cancel' });
        }
      }}
      onLostPointerCapture={(event) => {
        if (gesture.cancel(event.pointerId)) {
          setPreviewSize(0);
          recordUiEvent('edge-drag.end', { edge, phase: 'cancel' });
        }
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

const EDGES: Edge[] = ['left', 'right', 'top', 'bottom'];
const EDGE_LABELS: Record<Edge, string> = { left: '左侧', right: '右侧', top: '顶部', bottom: '底部' };
