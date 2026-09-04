import type {
  EditorSurfaceState,
  ExecutionMode,
  JsonValue,
  PlaytestEditorState,
} from "./types.ts";

export const executionModeLabels: Record<ExecutionMode, string> = {
  live: "LIVE · 当前真实运行",
  cached: "CACHED · 真实历史运行",
  mock: "MOCK · 确定性本地夹具",
  planned: "PLANNED · 尚未执行",
  blocked: "BLOCKED · 当前无法执行",
};

export const editorStateLabels: Record<EditorSurfaceState, string> = {
  loading: "正在加载 Playtest 数据…",
  empty: "尚无 Playtest 运行。",
  ready: "Playtest 数据已就绪。",
  failed: "Playtest 运行失败；日志和已完成证据仍被保留。",
  offline: "Playtest runner 未连接；可切换到明确标记的 Mock。",
  permission_denied: "没有查看或运行 Playtest 的权限。",
  disabled: "AI Playtest 模块已通过功能开关停用。",
};

export function editorStatus(
  state: EditorSurfaceState,
  mode: ExecutionMode,
): { stateLabel: string; modeLabel: string; isFailure: boolean } {
  return {
    stateLabel: editorStateLabels[state],
    modeLabel: executionModeLabels[mode],
    isFailure: state === "failed" || state === "offline" || state === "permission_denied",
  };
}

export const defaultPlaytestEditorState: PlaytestEditorState = {
  followLatest: true,
  trajectoryZoom: 1,
};

export function serializePlaytestEditorState(state: PlaytestEditorState): JsonValue {
  return { ...state };
}

export function restorePlaytestEditorState(value: JsonValue): PlaytestEditorState {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("playtest editor state must be an object");
  }
  const state = value as Record<string, JsonValue>;
  if (
    typeof state.followLatest !== "boolean"
    || typeof state.trajectoryZoom !== "number"
    || !Number.isFinite(state.trajectoryZoom)
    || state.trajectoryZoom <= 0
  ) {
    throw new TypeError("playtest editor state has invalid required fields");
  }
  const allowedFields = new Set([
    "followLatest",
    "selectedStepIndex",
    "selectedIssueId",
    "trajectoryZoom",
    "comparisonId",
    "baselineRunId",
    "candidateRunId",
  ]);
  if (Object.keys(state).some((key) => !allowedFields.has(key))) {
    throw new TypeError("playtest editor state contains unsupported fields");
  }
  if (
    state.selectedStepIndex !== undefined
    && (
      typeof state.selectedStepIndex !== "number"
      || !Number.isInteger(state.selectedStepIndex)
      || state.selectedStepIndex < 0
    )
  ) {
    throw new TypeError("selectedStepIndex must be a non-negative integer");
  }
  const stableId = /^[A-Za-z0-9][A-Za-z0-9._:-]*$/;
  for (const field of [
    "selectedIssueId",
    "comparisonId",
  ] as const) {
    const fieldValue = state[field];
    if (
      fieldValue !== undefined
      && (
        typeof fieldValue !== "string"
        || fieldValue.length < 3
        || fieldValue.length > 160
        || !stableId.test(fieldValue)
      )
    ) {
      throw new TypeError(`${field} must be a stable identifier`);
    }
  }
  for (const field of ["baselineRunId", "candidateRunId"] as const) {
    const fieldValue = state[field];
    if (
      fieldValue !== undefined
      && (
        typeof fieldValue !== "string"
        || fieldValue.length < 3
        || fieldValue.length > 96
        || !stableId.test(fieldValue)
      )
    ) {
      throw new TypeError(`${field} must be a valid run identifier`);
    }
  }
  const restored: PlaytestEditorState = {
    followLatest: state.followLatest,
    trajectoryZoom: state.trajectoryZoom,
  };
  if (typeof state.selectedStepIndex === "number") {
    restored.selectedStepIndex = state.selectedStepIndex;
  }
  for (const field of [
    "selectedIssueId",
    "comparisonId",
    "baselineRunId",
    "candidateRunId",
  ] as const) {
    const fieldValue = state[field];
    if (typeof fieldValue === "string") {
      restored[field] = fieldValue;
    }
  }
  return restored;
}
