import { useMemo, useState, useSyncExternalStore } from 'react';
import { uiDiagnosticBuffer, type UiDiagnosticEntry } from './diagnosticState';
import './debug-panel.css';

export interface DebugPanelProps {
  visible: boolean;
  onClose: () => void;
}

interface RuntimeInfo {
  viewport: { width: number; height: number; devicePixelRatio: number };
  browser: { userAgent: string; platform: string };
  renderer: { status: 'not-probed' };
}

function readRuntimeInfo(): RuntimeInfo {
  const viewport = {
    width: typeof window === 'undefined' ? 0 : window.innerWidth,
    height: typeof window === 'undefined' ? 0 : window.innerHeight,
    devicePixelRatio: typeof window === 'undefined' ? 1 : window.devicePixelRatio,
  };
  return {
    viewport,
    browser: {
      userAgent: typeof navigator === 'undefined' ? 'unavailable' : navigator.userAgent.slice(0, 300),
      platform: typeof navigator === 'undefined' ? 'unavailable' : navigator.platform.slice(0, 80),
    },
    renderer: { status: 'not-probed' },
  };
}

function createDiagnosticDocument(entries: readonly UiDiagnosticEntry[]) {
  return {
    schemaVersion: 1,
    capturedAt: new Date().toISOString(),
    storage: uiDiagnosticBuffer.storageStatus(),
    runtime: readRuntimeInfo(),
    entries,
  };
}

function downloadJson(value: unknown): void {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `sceneops-ui-diagnostics-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function EntryRow({ entry }: { entry: UiDiagnosticEntry }) {
  const time = entry.timestamp.slice(11, 23);
  const detail = entry.type === 'error'
    ? `${entry.summary} · ${entry.errorName}${entry.frames[0] ? ` · ${entry.frames[0]}` : ''}`
    : JSON.stringify(entry.fields);
  return <li className={entry.type === 'error' ? 'debug-panel__entry is-error' : 'debug-panel__entry'}>
    <time dateTime={entry.timestamp}>{time}</time>
    <strong>{entry.type}</strong>
    <span title={detail}>{detail}</span>
  </li>;
}

export function DebugPanel({ visible, onClose }: DebugPanelProps) {
  const entries = useSyncExternalStore(
    (listener) => uiDiagnosticBuffer.subscribe(listener),
    () => uiDiagnosticBuffer.snapshot(),
    () => [],
  );
  const [feedback, setFeedback] = useState('');
  const runtime = useMemo(() => visible ? readRuntimeInfo() : null, [visible]);
  if (!visible || !runtime) return null;
  const recent = entries.slice(-80).reverse();
  const errorCount = entries.filter((entry) => entry.type === 'error').length;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(createDiagnosticDocument(entries), null, 2));
      setFeedback('已复制诊断信息');
    } catch {
      setFeedback('复制失败，请使用导出 JSON');
    }
  };

  return <aside className="debug-panel" role="dialog" aria-modal="false" aria-label="界面诊断">
    <header className="debug-panel__header">
      <div><strong>界面诊断</strong><small>本机保存 · 最多 200 条 · {entries.length} 条 · {errorCount} 个错误</small></div>
      <button type="button" onClick={onClose} aria-label="关闭界面诊断">×</button>
    </header>
    <section className="debug-panel__runtime" aria-label="渲染环境">
      <span>{uiDiagnosticBuffer.storageStatus() === 'saved-locally' ? '诊断记录保存在本机，不会上传。' : '本机存储不可用；本次仅保存在内存，不影响工作台。'}</span>
      <span>视口 {runtime.viewport.width}×{runtime.viewport.height} · DPR {runtime.viewport.devicePixelRatio}</span>
      <span>{runtime.browser.platform} · {runtime.browser.userAgent}</span>
      <span>GPU renderer：未主动探测（避免创建新的 WebGL 上下文）</span>
    </section>
    <div className="debug-panel__actions">
      <button type="button" onClick={() => void copy()}>复制诊断</button>
      <button type="button" onClick={() => downloadJson(createDiagnosticDocument(entries))}>导出 JSON</button>
      <button type="button" onClick={() => { uiDiagnosticBuffer.clear(); setFeedback('本机诊断记录已清空'); }}>清空</button>
      <output aria-live="polite">{feedback}</output>
    </div>
    <ol className="debug-panel__entries" aria-label="最近诊断事件">
      {recent.length ? recent.map((entry, index) => <EntryRow key={`${entry.timestamp}-${index}`} entry={entry} />) : <li className="debug-panel__empty">暂无诊断事件</li>}
    </ol>
  </aside>;
}
