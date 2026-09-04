import type {
  HealthRowView,
  IntegrationHealthEditorState,
  IntegrationHealthEditorView,
  IntegrationHealthView,
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

function banner(state: IntegrationHealthEditorState): string {
  switch (state.phase) {
    case "loading":
      return "正在执行当前健康探测，不使用静态配置推断连接状态…";
    case "empty":
      return "尚未声明任何集成。";
    case "failed":
      return state.errorMessage ?? "健康查询失败；请查看关联日志。";
    case "disconnected":
      return state.errorMessage ?? "Integration Center API 已断开；显示内容不是当前 Live 健康状态。";
    case "permission_denied":
      return "缺少 integration:read 权限。";
    case "ready":
      return `已探测 ${state.integrations.length} 个集成；每项均显示证据模式与不可用原因。`;
  }
}

function healthRow(item: IntegrationHealthView, state: IntegrationHealthEditorState): HealthRowView {
  const logs = state.recentLogs.filter((log) => log.integrationId === item.integrationId);
  const currentJob = item.currentJob;
  const evidenceWarning = item.liveActionsEnabled
    ? ""
    : item.mode !== "live" || !item.isCurrent
      ? `该结果为 ${MODE_LABEL[item.mode]} 或已经过期，不能启用 Live 操作。`
      : "当前状态未满足 connected/busy Live 操作前置条件。";
  return {
    id: item.integrationId,
    name: item.displayName,
    state: item.state,
    stateLabel: STATE_LABEL[item.state],
    modeLabel: MODE_LABEL[item.mode],
    versionLabel: `工具 ${item.toolVersion ?? "未报告"} · 适配器 ${item.adapterVersion ?? "未报告"}`,
    capabilityLabel: item.capabilityIds.length ? item.capabilityIds.join(" · ") : "未报告能力",
    lastSeenLabel: item.lastSeenAt ? `最后出现：${item.lastSeenAt}` : "尚无最后在线时间",
    jobLabel: currentJob
      ? `${currentJob.title} · ${currentJob.state} · ${Math.round(currentJob.progress * 100)}% · ${currentJob.correlationId}`
      : "当前无任务",
    queueLabel: `排队 ${item.queue.depth} · 运行 ${item.queue.running}`,
    explanation: [item.reason, evidenceWarning].filter(Boolean).join(" ") || "当前健康探测可用。",
    actions: item.recommendedActions,
    logs,
  };
}

export function createIntegrationHealthEditorView(
  state: IntegrationHealthEditorState,
): IntegrationHealthEditorView {
  const query = state.searchText.trim().toLocaleLowerCase();
  const rows = state.integrations
    .filter((item) => !query || `${item.displayName} ${item.integrationId} ${item.capabilityIds.join(" ")}`.toLocaleLowerCase().includes(query))
    .map((item) => healthRow(item, state));
  return {
    editorId: "integration.health",
    title: "集成健康",
    status: state.phase,
    banner: banner(state),
    rows,
  };
}

export default createIntegrationHealthEditorView;
