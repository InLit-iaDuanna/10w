import type {
  ContextBinding,
  ExecutionMode,
  LogicEditorState,
  LogicEditorStatus,
} from "./editorTypes.ts";

const STATUSES = new Set<LogicEditorStatus>([
  "loading",
  "empty",
  "ready",
  "failed",
  "offline",
  "permission_denied",
]);

const MODES = new Set<ExecutionMode>([
  "live",
  "cached",
  "mock",
  "planned",
  "blocked",
]);

export function createLogicEditorState(
  status: LogicEditorStatus = "loading",
  mode: ExecutionMode = "planned",
  contextBinding: ContextBinding = { mode: "follow-global" },
): LogicEditorState {
  return {
    schemaVersion: 1,
    status,
    mode,
    contextBinding,
    selectedEntityIds: [],
  };
}

export function serializeLogicEditorState(
  state: LogicEditorState,
): Record<string, unknown> {
  return {
    schemaVersion: state.schemaVersion,
    status: state.status,
    mode: state.mode,
    contextBinding: structuredClone(state.contextBinding),
    selectedEntityIds: [...state.selectedEntityIds],
    ...(state.errorCode ? { errorCode: state.errorCode } : {}),
  };
}

export function restoreLogicEditorState(value: unknown): LogicEditorState {
  if (!isRecord(value) || value.schemaVersion !== 1) {
    throw new TypeError("Logic editor state requires schemaVersion 1.");
  }
  if (!STATUSES.has(value.status as LogicEditorStatus)) {
    throw new TypeError("Logic editor state has an invalid status.");
  }
  if (!MODES.has(value.mode as ExecutionMode)) {
    throw new TypeError("Logic editor state has an invalid execution mode.");
  }
  if (!isContextBinding(value.contextBinding)) {
    throw new TypeError("Logic editor state has an invalid context binding.");
  }
  if (
    !Array.isArray(value.selectedEntityIds) ||
    !value.selectedEntityIds.every((item) => typeof item === "string")
  ) {
    throw new TypeError("Logic editor state has invalid selected entity IDs.");
  }
  if (value.errorCode !== undefined && typeof value.errorCode !== "string") {
    throw new TypeError("Logic editor state has an invalid error code.");
  }
  return {
    schemaVersion: 1,
    status: value.status as LogicEditorStatus,
    mode: value.mode as ExecutionMode,
    contextBinding: structuredClone(value.contextBinding),
    selectedEntityIds: [...value.selectedEntityIds],
    ...(value.errorCode ? { errorCode: value.errorCode } : {}),
  };
}

function isContextBinding(value: unknown): value is ContextBinding {
  if (!isRecord(value)) return false;
  if (value.mode === "follow-global") return true;
  return value.mode === "pinned" && isRecord(value.context);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
