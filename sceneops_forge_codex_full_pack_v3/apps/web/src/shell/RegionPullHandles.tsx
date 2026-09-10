import { useEffect, useRef, useState } from 'react';
import { createPortal, flushSync } from 'react-dom';
import { ElasticRegionPreview } from './ElasticRegionPreview';
import type { RegionPlacementOrigin } from './regionPreviewGeometry';
import type { Edge } from '@sceneops/forge-shell';

export type RegionSplitRequest = (instanceId: string, edge: Edge, size?: number, origin?: RegionPlacementOrigin) => Promise<void>;
export type RegionCollapseRequest = (instanceId: string, edge: Edge, crossRatio: number) => Promise<void>;
type Point = { x: number; y: number };

/** Hover previews a split; only the confirmation click asks Dockview to lay it out. */
export function RegionPullHandles({ instanceId, split, getBounds, onPhaseChange, onPlaced }: {
  instanceId: string;
  split: RegionSplitRequest;
  getBounds(): DOMRect;
  onPhaseChange?(phase: 'idle' | 'hover' | 'ready'): void;
  onPlaced?(): void;
}) {
  const [edge, setEdge] = useState<Edge | null>(null);
  const [ready, setReady] = useState(false);
  const [point, setPoint] = useState<Point>({ x: 0, y: 0 });
  const [retracting, setRetracting] = useState(false);
  const committing = useRef(false);
  const [confirming, setConfirming] = useState(false);
  const shoulder = useRef(90);
  const revealStarted = useRef(0);
  const mounted = useRef(true);
  const pulled = useRef(false);
  const blockedEdge = useRef<Edge | null>(null);
  const [error, setError] = useState('');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const host = useRef<HTMLButtonElement | null>(null);
  const clearTimer = () => { if (timer.current !== null) clearTimeout(timer.current); timer.current = null; };
  const cancel = () => {
    if (committing.current) return;
    clearTimer(); setReady(false); pulled.current = false;
    if (ready) {
      blockedEdge.current = edge; setRetracting(true);
      timer.current = setTimeout(() => { timer.current = null; setEdge(null); setRetracting(false); }, 260);
    } else { setEdge(null); setRetracting(false); }
  };
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; clearTimer(); }; }, []);
  useEffect(() => {
    if (!edge) return;
    const win = host.current?.ownerDocument.defaultView;
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { event.preventDefault(); cancel(); } };
    win?.addEventListener('keydown', escape);
    win?.addEventListener('blur', cancel);
    return () => { win?.removeEventListener('keydown', escape); win?.removeEventListener('blur', cancel); };
  }, [edge, ready]);
  useEffect(() => { onPhaseChange?.(ready ? 'ready' : edge ? 'hover' : 'idle'); }, [ready, edge, onPhaseChange]);
  const bounds = edge ? getBounds() : null;
  const horizontal = edge === 'left' || edge === 'right';
  const size = bounds ? Math.max(0, Math.min(horizontal ? bounds.width : bounds.height,
    edge === 'left' ? point.x - bounds.left : edge === 'right' ? bounds.right - point.x
      : edge === 'top' ? point.y - bounds.top : bounds.bottom - point.y)) : 0;
  const confirm = () => {
    if (committing.current) return;
    if (!edge || !ready || !bounds || size < 24) { cancel(); return; }
    const selectedEdge = edge;
    committing.current = true; clearTimer(); pulled.current = false;
    revealStarted.current = host.current!.ownerDocument.defaultView!.performance.now();
    setConfirming(true);
    const releasePreview = () => {
      if (mounted.current) flushSync(() => { setEdge(null); setReady(false); setConfirming(false); });
    };
    void split(instanceId, selectedEdge, size, { ...point, shoulder: shoulder.current, startedAt: revealStarted.current, onPrepared: releasePreview }).then(() => {
      if (mounted.current) onPlaced?.();
    }).catch(reason => {
      if (mounted.current) setError(reason instanceof Error ? reason.message : String(reason));
    }).finally(() => { releasePreview(); committing.current = false; });
  };
  return <>
    {(['bottom', 'left', 'right'] as const).map(side => <button key={side} type="button"
      className={`forge-edge-handle forge-region-pull forge-edge-${side}`}
      aria-label={`在工作区${LABELS[side]}拉出功能`} data-region-instance={instanceId}
      onPointerEnter={event => {
        if (committing.current || ready || retracting || blockedEdge.current === side || event.pointerType === 'touch' || event.buttons) return;
        clearTimer(); host.current = event.currentTarget; setError(''); setEdge(side);
        setPoint({ x: event.clientX, y: event.clientY });
        timer.current = setTimeout(() => { timer.current = null; setReady(true); }, 650);
      }}
      onPointerMove={event => { if (!ready && !retracting) setPoint({ x: event.clientX, y: event.clientY }); }}
      onPointerLeave={() => { blockedEdge.current = null; if (!ready && !retracting) cancel(); }}
      onKeyDown={event => {
        if (committing.current) return;
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault(); clearTimer(); host.current = event.currentTarget;
        const rect = getBounds(); setPoint({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
        setRetracting(false); setEdge(side); setReady(true);
      }}
    />)}
    {edge && bounds && host.current && createPortal(ready || retracting ? <div className={retracting ? 'forge-hover-retraction' : `forge-hover-placement${confirming ? ' is-confirming' : ''}`}
      onPointerMove={event => {
        if (retracting || committing.current) return;
        const distance = edge === 'left' ? event.clientX - bounds.left : edge === 'right' ? bounds.right - event.clientX
          : edge === 'top' ? event.clientY - bounds.top : bounds.bottom - event.clientY;
        if (distance >= 24) pulled.current = true;
        if (pulled.current && distance <= 10) { cancel(); return; }
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) { cancel(); return; }
        setPoint({ x: event.clientX, y: event.clientY });
      }}
      onPointerLeave={() => { if (!retracting) cancel(); }}
      onPointerDown={event => { event.preventDefault(); event.stopPropagation(); }}
      onClick={event => { event.preventDefault(); event.stopPropagation(); confirm(); }}
      onContextMenu={event => { event.preventDefault(); cancel(); }}>
      <ElasticRegionPreview edge={edge} bounds={bounds} point={point} size={size} frozen={confirming} expandingSince={confirming ? revealStarted.current : undefined} onShoulderChange={width => { shoulder.current = width; }} />
      {!retracting && !confirming && <div className="forge-hover-tool-card is-ready" style={{ left: Math.min(Math.max(bounds.left, point.x + 14), bounds.right - 144),
        top: Math.min(Math.max(bounds.top, point.y + 14), bounds.bottom - 64) }}><SplitGlyph edge={edge} /><span>点击创建 · 推回取消</span></div>}
    </div> : <div className="forge-hover-tool-card" style={{
      left: Math.min(Math.max(bounds.left, point.x + 10), bounds.right - 44),
      top: Math.min(Math.max(bounds.top, point.y + 10), bounds.bottom - 34),
    }}><SplitGlyph edge={edge} /></div>, host.current.ownerDocument.body)}
    {error && <p className="forge-hover-error" role="alert">{error}</p>}
  </>;
}

function SplitGlyph({ edge }: { edge: Edge }) {
  return <svg viewBox="0 0 32 24" fill="none" aria-hidden="true">
    <rect x="2" y="2" width="28" height="20" rx="3" />
    {edge === 'left' || edge === 'right' ? <path d={edge === 'left' ? 'M12 2v20' : 'M20 2v20'} />
      : <path d={edge === 'top' ? 'M2 10h28' : 'M2 14h28'} />}
  </svg>;
}
const LABELS: Record<Edge, string> = { top: '上方', bottom: '下方', left: '左侧', right: '右侧' };
