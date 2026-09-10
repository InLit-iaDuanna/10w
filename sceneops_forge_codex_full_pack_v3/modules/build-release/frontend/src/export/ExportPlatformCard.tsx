import { useState } from 'react';
import type { ExportPlatform, ExportTask } from './client';

export const platformNames: Record<ExportPlatform, string> = {
  android: 'Android · APK', 'mac-arm64': 'macOS · Apple Silicon', 'mac-x64': 'macOS · Intel', 'win-x64': 'Windows · x64',
};
const statuses: Record<string, string> = { pending: '等待 Agent 导出', queued: '等待执行', running: '正在导出', succeeded: '包已生成', failed: '导出失败', cancelled: '已取消', interrupted: '已中断', blocked: '需要处理' };
export function ExportPlatformCard({ platform, busy, onAction, onVerify }: {
  platform: ExportTask['platforms'][number]; busy: boolean;
  onAction: (platform: ExportPlatform, action: 'continue' | 'cancel') => void;
  onVerify: (platform: ExportPlatform, status: 'passed' | 'failed', notes: string, device: string, attemptId: string) => void;
}) {
  const [notes, setNotes] = useState('');
  const [device, setDevice] = useState('');
  const attemptId = platform.attempts?.at(-1)?.id;
  const cancelling = platform.attempts?.at(-1)?.cancel_requested ?? false;
  const active = ['queued', 'running'].includes(platform.status);
  return <article className="export-platform">
    <header><strong>{platformNames[platform.platform]}</strong><span role="status">{statuses[platform.status] ?? platform.status}</span></header>
    <p className="export-muted">{platform.verification === 'passed' ? '设备验证通过（人工记录）' : platform.verification === 'failed' ? '设备验证未通过' : '待设备验证'}</p>
    {platform.verification_notes && <p>{platform.verification_notes}</p>}
    {platform.attempts?.map(attempt => <section key={attempt.id} className="export-attempt">
      <p>第 {attempt.number} 次 · {statuses[attempt.status] ?? attempt.status} · {attempt.stage}</p>
      {attempt.error && <p role="alert" className="export-error">{attempt.error}</p>}
      {attempt.artifacts?.map(artifact => <a className="export-download" key={artifact.id} href={artifact.download_url} download>{artifact.name} · {(artifact.size / 1024 / 1024).toFixed(1)} MB ↓</a>)}
      <details><summary>查看日志（{attempt.logs?.length ?? 0}）</summary><pre>{attempt.logs?.map(log => `${log.timestamp} [${log.stage}] ${log.message}`).join('\n') || '尚无日志'}</pre></details>
    </section>)}
    <div className="export-actions">{active ? <button disabled={busy || cancelling} onClick={() => onAction(platform.platform, 'cancel')}>{cancelling ? '正在取消…' : '取消此平台'}</button>
      : ['failed', 'cancelled', 'interrupted', 'blocked'].includes(platform.status) && <button disabled={busy} onClick={() => onAction(platform.platform, 'continue')}>继续导出此平台</button>}</div>
    {platform.status === 'succeeded' && <details><summary>记录设备验证</summary>
      <p className="export-muted">在目标设备实际安装或解压后，检查启动、输入和主要游戏交互，再记录结果。</p>
      <input aria-label={`${platformNames[platform.platform]}验证设备`} placeholder="设备与系统版本" value={device} onChange={event => setDevice(event.target.value)} />
      <textarea aria-label={`${platformNames[platform.platform]}验证记录`} placeholder="设备、系统版本和实际测试结果" value={notes} onChange={event => setNotes(event.target.value)} />
      <div className="export-actions"><button disabled={busy || !notes.trim() || !device.trim() || !attemptId} onClick={() => onVerify(platform.platform, 'passed', notes, device, attemptId!)}>记录验证通过</button><button disabled={busy || !notes.trim() || !device.trim() || !attemptId} onClick={() => onVerify(platform.platform, 'failed', notes, device, attemptId!)}>记录验证失败</button></div>
    </details>}
  </article>;
}
