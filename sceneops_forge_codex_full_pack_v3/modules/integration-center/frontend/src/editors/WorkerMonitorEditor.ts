import type {
  JobView,
  RecommendedActionView,
  WorkerMonitorEditorState,
  WorkerMonitorEditorView,
  WorkerRowView,
  WorkerView,
} from "../types.ts";

const STATE_LABEL = {
  connected: "已连接",
  disconnected: "已断开",
  degraded: "性能下降",
  incompatible: "不兼容",
  busy: "忙碌",
  unauthorized: "未授权",
  unknown: "未知",
} as const;

const MODE_LABEL = {
  live: "LIVE",
  cached: "CACHED",
  mock: "MOCK",
  planned: "PLANNED",
  blocked: "BLOCKED",
} as const;

function recoveryActions(
  mode: WorkerView["mode"],
  isCurrent: boolean,
  job?: JobView,
): RecommendedActionView[] {
  if (!job) return [];
  const live = mode === "live" && isCurrent;
  const unavailableEvidence = mode !== "live"
    ? "只有 Live Worker 可发送恢复控制命令。"
    : "Worker 心跳证据已过期；请先刷新状态。";
  const active = ["queued", "running", "paused", "failed", "timed_out", "cancel_requested"].includes(job.state);
  const retryState = ["failed", "timed_out"].includes(job.state);
  const retrySafe = job.retrySafety !== "non_idempotent";
  const resumeState = ["paused", "failed", "timed_out"].includes(job.state);
  return [
    {
      commandId: "job.cancel",
      label: "取消",
      available: live && active && job.state !== "cancel_requested",
      unavailableReason: !live
        ? unavailableEvidence
        : job.state === "cancel_requested"
          ? "取消已请求，等待外部状态对账。"
          : !active
            ? "任务已经结束。"
            : undefined,
    },
    {
      commandId: "job.retry",
      label: "重试",
      available: live && retryState && retrySafe,
      unavailableReason: !live
        ? unavailableEvidence
        : !retryState
        ? "只有失败或超时任务可重试。"
        : !retrySafe
          ? "非幂等操作禁止盲目重试；请先对账或使用恢复检查点。"
          : undefined,
    },
    {
      commandId: "job.resume",
      label: "恢复",
      available: live && resumeState && job.resumeTokenAvailable,
      unavailableReason: !live
        ? unavailableEvidence
        : !resumeState
        ? "任务当前不在可恢复状态。"
        : !job.resumeTokenAvailable
          ? "适配器未提供恢复检查点。"
          : undefined,
    },
  ];
}

function banner(state: WorkerMonitorEditorState): string {
  switch (state.phase) {
    case "loading":
      return "正在加载 Worker 心跳、任务与队列…";
    case "empty":
      return "当前项目没有注册 Worker。";
    case "failed":
      return state.errorMessage ?? "Worker 查询失败。";
    case "disconnected":
      return state.errorMessage ?? "Worker 事件连接已断开；可重连但不会伪造 Live 心跳。";
    case "permission_denied":
      return "缺少 job:read 权限。";
    case "ready":
      return `正在监控 ${state.workers.length} 个 Worker。`;
  }
}

function workerRow(worker: WorkerView, state: WorkerMonitorEditorState): WorkerRowView {
  const job = worker.currentJob;
  return {
    id: worker.workerId,
    name: worker.displayName,
    lifecycleLabel: worker.lifecycle,
    stateLabel: STATE_LABEL[worker.healthState],
    modeLabel: MODE_LABEL[worker.mode],
    versionLabel: `Worker ${worker.workerVersion}`,
    capabilityLabel: worker.capabilityIds.length
      ? worker.capabilityIds.join(" · ")
      : "未报告能力",
    freshnessLabel: worker.isCurrent
      ? `快照有效至：${worker.expiresAt}`
      : `快照已过期（观测：${worker.observedAt}）`,
    heartbeatLabel: worker.lastHeartbeatAt ? `最后心跳：${worker.lastHeartbeatAt}` : "尚无心跳",
    jobLabel: job
      ? `${job.title} · ${job.state} · ${Math.round(job.progress * 100)}% · ${job.correlationId}`
      : "当前无任务",
    queueLabel: `排队 ${worker.queue.depth} · 运行 ${worker.queue.running}`,
    actions: worker.recommendedActions,
    recoveryActions: recoveryActions(worker.mode, worker.isCurrent, job),
    logs: state.recentLogs.filter((log) => log.integrationId === worker.integrationId),
  };
}

export function createWorkerMonitorEditorView(state: WorkerMonitorEditorState): WorkerMonitorEditorView {
  const query = state.searchText.trim().toLocaleLowerCase();
  const rows = state.workers
    .filter((worker) => !query || `${worker.displayName} ${worker.workerId} ${worker.integrationId}`.toLocaleLowerCase().includes(query))
    .map((worker) => workerRow(worker, state));
  return {
    editorId: "worker.monitor",
    title: "Worker 监控",
    status: state.phase,
    banner: banner(state),
    rows,
  };
}

export default createWorkerMonitorEditorView;
