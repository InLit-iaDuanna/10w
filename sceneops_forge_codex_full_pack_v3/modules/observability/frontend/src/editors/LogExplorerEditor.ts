import type {
  EditorActionView,
  LogExplorerState,
  LogExplorerView,
  LogRowView,
  StructuredLogView,
} from "../types.ts";

const MODE_LABELS = {
  live: "LIVE",
  cached: "CACHED",
  mock: "MOCK",
  planned: "PLANNED",
  blocked: "BLOCKED",
} as const;

function row(item: StructuredLogView): LogRowView {
  const trace = item.context;
  const correlation = [
    trace.projectId,
    trace.runId,
    trace.jobId,
    trace.correlationId,
    trace.causationId,
  ]
    .filter(Boolean)
    .join(" · ");
  const source = [item.sourceModule, item.sourceTool, item.workerId].filter(Boolean).join(" / ");
  return {
    id: item.eventId,
    primary: `${item.emittedAt}  ${item.message}`,
    secondary: source,
    level: item.level,
    modeLabel: MODE_LABELS[item.mode],
    correlationLabel: correlation,
    fields: Object.entries(item.fields).map(([key, value]) => `${key}=${String(value)}`),
    artifacts: item.artifactLinks,
  };
}

function banner(state: LogExplorerState): string {
  switch (state.phase) {
    case "loading":
      return "正在加载结构化日志…";
    case "empty":
      return "当前筛选条件下没有日志。";
    case "failed":
      return state.errorMessage ?? "日志查询失败。";
    case "disconnected":
      return state.errorMessage ?? "事件连接已断开；可使用游标安全重连。";
    case "permission_denied":
      return "缺少 observability:read 权限，无法查看日志。";
    case "ready":
      return `已加载 ${state.items.length} 条日志；项目、运行、任务与关联 ID 保持可检索。`;
  }
}

export function createLogExplorerView(state: LogExplorerState): LogExplorerView {
  const actions: EditorActionView[] = [
    {
      commandId: "observability.logs.search",
      label: state.phase === "disconnected" ? "重新连接" : "搜索",
      available: state.phase !== "permission_denied" && state.phase !== "loading",
      unavailableReason:
        state.phase === "permission_denied"
          ? "缺少 observability:read 权限。"
          : state.phase === "loading"
            ? "等待当前查询完成。"
            : undefined,
    },
    {
      commandId: "observability.diagnostic.export",
      label: "下载诊断包",
      available: state.canExportDiagnostics,
      unavailableReason: state.canExportDiagnostics
        ? undefined
        : state.exportUnavailableReason ?? "缺少 observability:export 权限。",
    },
  ];
  return {
    editorId: "observability.logs",
    title: "日志与追踪",
    status: state.phase,
    banner: banner(state),
    rows: state.items.map(row),
    actions,
    selectableText: true,
  };
}

export default createLogExplorerView;
