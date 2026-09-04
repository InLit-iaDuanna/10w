import { useEffect, useRef } from 'react';
import type { Health, Snapshot, Worker, Evidence } from './api';

export const labels: Record<string, string> = {
  connected: '已连接', disconnected: '已断开', degraded: '降级', incompatible: '不兼容',
  busy: '忙碌', unauthorized: '未授权', unknown: '未知', running: '运行中', succeeded: '已完成',
  failed: '失败', queued: '排队', online: '在线', offline: '离线', draining: '排空中',
};
export function Mode({ value = 'mock' }: { value?: string }) {
  return <span className={`mode mode-${value}`}>{value.toUpperCase()}</span>;
}

export function IntegrationDetails({ item, onClose, onLogs }: {
  item: Health; onClose: () => void; onLogs: () => void;
}) {
  return <section className="ops-panel detail-panel"><div className="panel-heading"><h2>{item.display_name} <Mode value={item.evidence.mode}/></h2><button onClick={onClose}>收起</button></div>
    <p>{item.safe_reason || '固定健康样例，仅用于检查状态展示。'}</p>
    <dl><div><dt>工具 / 适配器版本</dt><dd>{item.tool_version} / {item.adapter_version}</dd></div>
      <div><dt>观测时间</dt><dd>{item.observed_at}</dd></div><div><dt>有效期至</dt><dd>{item.expires_at}</dd></div>
      <div><dt>最后在线</dt><dd>{item.last_seen_at || '未记录'}</dd></div>
      <div><dt>熔断器</dt><dd>{item.circuit.state} · 连续失败 {item.circuit.consecutive_failures}</dd></div>
    </dl><h3>报告能力</h3><div className="chips">{item.capability_ids.map(id => <code key={id}>{id}</code>)}</div>
    <h3>允许的命令标识</h3><div className="chips">{item.allowlisted_command_ids.map(id => <code key={id}>{id}</code>)}</div>
    <p className="muted">Mock 证据不能启用真实工具操作。请在接入真实适配器并获取当前健康结果后再执行恢复。</p>
    <button onClick={onLogs}>查看关联作业日志 ↓</button>
  </section>;
}

export function WorkerPanel({ workers, onJob }: { workers: Worker[]; onJob: (id: string) => void }) {
  return <section className="ops-panel"><div className="panel-heading"><h2>Worker 监视器 <small>{workers.length} 个</small></h2><span className="muted">固定心跳快照</span></div>
    {!workers.length && <p className="empty">当前项目 / 筛选下没有 Worker。</p>}
    {workers.map(worker => <article className="worker" key={worker.worker_id}>
      <div className="worker-heading"><strong>{worker.display_name}</strong><span>{labels[worker.lifecycle] || worker.lifecycle} <Mode value={worker.evidence.mode}/></span></div>
      <div className="worker-meta">v{worker.worker_version} · 队列 {worker.queue.depth} · 执行中 {worker.queue.running}</div>
      <div className="chips">{worker.capability_ids.map(id => <code key={id}>{id}</code>)}</div>
      <small>心跳 {worker.last_heartbeat_at || '未记录'}</small>
      {worker.current_job && <button className="text-button" onClick={() => onJob(worker.current_job!.job_id)}>查看 {worker.current_job.title} →</button>}
      <details><summary>恢复与重启说明</summary><p>当前为 Mock，取消、重试、恢复与重启均不可执行。真实恢复前需确认任务状态、对账外部副作用、保留已完成步骤，并由授权操作者执行。</p></details>
    </article>)}
  </section>;
}

export function ProgressPanel({ events, onJob }: { events: Snapshot['progress']; onJob: (id: string) => void }) {
  const latest = new Map<string, Snapshot['progress'][number]>();
  for (const event of events) latest.set(event.context.job_id || event.event_id, event);
  return <section className="ops-panel"><div className="panel-heading"><h2>作业进度</h2><span className="muted">样例进度 · 不自动推进</span></div>
    {!latest.size && <p className="empty">当前筛选下没有进度事件。</p>}
    {[...latest.values()].map(event => <article className="job" key={event.event_id}>
      <div className="worker-heading"><button className="text-button" onClick={() => onJob(event.context.job_id!)}>{event.context.job_id}</button><span className={`state state-${event.state}`}>{labels[event.state] || event.state}</span></div>
      <div className="progress-line"><progress value={event.progress} max="1" aria-label={`${event.context.job_id} 进度`}/><b>{Math.round(event.progress * 100)}%</b></div>
      <p>{event.message}</p><Mode value={event.mode}/>
    </article>)}
  </section>;
}

export function EvidenceDialog({ data, error, onClose }: { data?: Evidence; error: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { ref.current?.showModal(); }, []);
  return <dialog ref={ref} onCancel={onClose} className="evidence-dialog"><div className="panel-heading"><h2>本地证据 <Mode/></h2><button onClick={onClose}>关闭</button></div>
    {error ? <p role="alert">证据加载失败，请关闭后重试。</p> : data ? <><p>{data.description}</p><code>{data.artifact_id}</code><pre>{JSON.stringify(data.records, null, 2)}</pre></> : <p role="status">正在加载证据…</p>}
  </dialog>;
}
