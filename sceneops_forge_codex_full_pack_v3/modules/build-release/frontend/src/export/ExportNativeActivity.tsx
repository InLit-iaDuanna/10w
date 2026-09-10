import type { ExportTask } from './client';

const labels: Record<string, string> = {
  queued: 'Agent 排队中', running: 'Agent 正在操作电脑', cancel_pending: '正在停止 Agent',
  succeeded: 'Agent 执行结束', failed: 'Agent 执行失败', cancelled: 'Agent 已停止', interrupted: 'Agent 执行已中断',
};

export function ExportNativeActivity({ runs }: { runs: NonNullable<ExportTask['native_runs']> }) {
  return <section className="export-native-activity" aria-label="Agent 电脑操作记录">{runs.map(run => {
    const logs = run.logs ?? [];
    const active = ['queued', 'running', 'cancel_pending'].includes(run.status);
    return <article className="export-native-run" key={run.id}>
      <p role={active ? 'status' : undefined}>{run.cancel_requested && active ? '正在停止 Agent' : labels[run.status] ?? run.status}</p>
      {run.agent_task_id && <small className="export-muted">执行任务：{run.agent_task_id}</small>}
      {!!logs.length && <details open={active}><summary>查看实际操作记录（{logs.length}）</summary>{logs.map((log, index) => <pre key={`${log.timestamp}:${index}`}><time>{new Date(log.timestamp).toLocaleTimeString()}</time> {log.message}</pre>)}</details>}
      {run.error && <p role="alert" className="export-error">{run.error}</p>}
    </article>;
  })}</section>;
}
