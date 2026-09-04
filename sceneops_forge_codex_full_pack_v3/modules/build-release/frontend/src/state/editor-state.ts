export const EDITOR_IDS = [
  "build.matrix",
  "build.console",
  "release.gates",
  "release.center",
  "release.patch-notes",
] as const;

export type EditorId = (typeof EDITOR_IDS)[number];
export type ViewState =
  | "loading"
  | "empty"
  | "ready"
  | "failed"
  | "offline"
  | "permission_denied";
export type ExecutionMode = "live" | "cached" | "mock" | "planned" | "blocked";

export interface StructuredError {
  code: string;
  message: string;
  requestId?: string;
  retryable: boolean;
  suggestedActions: string[];
}

export interface EditorSnapshot {
  view: ViewState;
  mode: ExecutionMode;
  headline?: string;
  detail?: string;
  integrationId?: string;
  error?: StructuredError;
  blockingGateCount?: number;
}

export interface EditorLocalState {
  selectedId: string | null;
  filter: string;
  followTail: boolean;
  expandedIds: string[];
  activeTab: string;
}

export interface EditorActionModel {
  commandId: string;
  label: string;
  disabled: boolean;
  reason?: string;
}

export interface EditorViewModel {
  stateLabel: string;
  modeLabel: string;
  headline: string;
  detail: string;
  action?: EditorActionModel;
}

export const DEFAULT_LOCAL_STATE: Readonly<EditorLocalState> = {
  selectedId: null,
  filter: "",
  followTail: true,
  expandedIds: [],
  activeTab: "overview",
};

const VIEW_LABELS: Record<ViewState, string> = {
  loading: "正在加载",
  empty: "暂无数据",
  ready: "已就绪",
  failed: "执行失败",
  offline: "集成离线",
  permission_denied: "权限不足",
};

export const MODE_PRESENTATION: Record<
  ExecutionMode,
  Readonly<{ icon: string; label: string }>
> = {
  live: { icon: "●", label: "LIVE · 实时执行" },
  cached: { icon: "◷", label: "CACHED · 历史实跑缓存" },
  mock: { icon: "⚗", label: "MOCK · 确定性模拟" },
  planned: { icon: "○", label: "PLANNED · 尚未执行" },
  blocked: { icon: "⛔", label: "BLOCKED · 当前受阻" },
};

export function restoreEditorState(value: unknown): EditorLocalState {
  if (!isRecord(value)) return { ...DEFAULT_LOCAL_STATE, expandedIds: [] };
  return {
    selectedId: typeof value.selectedId === "string" ? value.selectedId : null,
    filter: typeof value.filter === "string" ? value.filter : "",
    followTail: typeof value.followTail === "boolean" ? value.followTail : true,
    expandedIds: Array.isArray(value.expandedIds)
      ? value.expandedIds.filter((item): item is string => typeof item === "string")
      : [],
    activeTab: typeof value.activeTab === "string" ? value.activeTab : "overview",
  };
}

export function serializeEditorState(state: EditorLocalState): EditorLocalState {
  return restoreEditorState(JSON.parse(JSON.stringify(state)));
}

export function buildEditorViewModel(snapshot: EditorSnapshot): EditorViewModel {
  const mode = MODE_PRESENTATION[snapshot.mode];
  const base = {
    stateLabel: VIEW_LABELS[snapshot.view],
    modeLabel: `${mode.icon} ${mode.label}`,
    headline: snapshot.headline ?? VIEW_LABELS[snapshot.view],
    detail: snapshot.detail ?? "",
  };
  if (snapshot.view === "offline") {
    return {
      ...base,
      detail: snapshot.detail ?? `未连接 ${snapshot.integrationId ?? "所需集成"}。`,
      action: {
        commandId: "integration.open",
        label: "打开集成中心",
        disabled: false,
      },
    };
  }
  if (snapshot.view === "failed" && snapshot.error) {
    return {
      ...base,
      headline: `${snapshot.error.code} · ${snapshot.error.message}`,
      detail: snapshot.error.requestId
        ? `请求 ID：${snapshot.error.requestId}`
        : base.detail,
      action: snapshot.error.retryable
        ? {
            commandId: snapshot.error.suggestedActions[0] ?? "release.deploy.retry",
            label: "重试",
            disabled: false,
          }
        : undefined,
    };
  }
  if (snapshot.view === "permission_denied") {
    return { ...base, detail: snapshot.detail ?? "请联系项目管理员授予所需权限。" };
  }
  if ((snapshot.blockingGateCount ?? 0) > 0) {
    return {
      ...base,
      action: {
        commandId: "release.deploy",
        label: "发布",
        disabled: true,
        reason: `${snapshot.blockingGateCount} 个阻断门禁尚未通过`,
      },
    };
  }
  return base;
}

export function plannedSnapshot(editorName: string): EditorSnapshot {
  return {
    view: "empty",
    mode: "planned",
    headline: `${editorName} 尚无记录`,
    detail: "连接模块运行时与生成的 API 客户端后，可在此加载项目数据。",
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
