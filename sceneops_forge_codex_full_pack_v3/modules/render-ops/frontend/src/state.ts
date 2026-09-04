import type {
  ContextBinding,
  EditorStatus,
  ExecutionMode,
  RenderEditorLocalState,
  RenderEditorServerState,
} from "./contracts.ts";

const statuses = new Set<EditorStatus>([
  "loading",
  "empty",
  "ready",
  "failed",
  "offline",
  "permission-denied",
]);
const modes = new Set<ExecutionMode>([
  "live",
  "cached",
  "mock",
  "planned",
  "blocked",
]);

export const defaultEditorState: RenderEditorLocalState = {
  schemaVersion: 1,
  status: "empty",
  executionMode: "planned",
  selectedId: null,
  activeTab: "overview",
  filter: "",
  errorCode: null,
  contextBinding: { mode: "follow-global" },
  visible: true,
};

function restoreContext(value: unknown): ContextBinding {
  if (!value || typeof value !== "object") return { mode: "follow-global" };
  const candidate = value as Record<string, unknown>;
  if (candidate.mode === "pinned" && candidate.context && typeof candidate.context === "object") {
    const source = candidate.context as Record<string, unknown>;
    const context: { projectId?: string; sceneId?: string; activeRenderJobId?: string } = {};
    if (typeof source.projectId === "string") context.projectId = source.projectId;
    if (typeof source.sceneId === "string") context.sceneId = source.sceneId;
    if (typeof source.activeRenderJobId === "string") {
      context.activeRenderJobId = source.activeRenderJobId;
    }
    return {
      mode: "pinned",
      context,
    };
  }
  return { mode: "follow-global" };
}

export function serializeEditorState(state: RenderEditorLocalState): unknown {
  return {
    schemaVersion: 1,
    selectedId: state.selectedId,
    activeTab: state.activeTab,
    filter: state.filter,
    contextBinding: state.contextBinding,
    visible: state.visible,
  };
}

export function restoreEditorState(value: unknown): RenderEditorLocalState {
  if (!value || typeof value !== "object") return { ...defaultEditorState };
  const candidate = value as Record<string, unknown>;
  return {
    schemaVersion: 1,
    status: defaultEditorState.status,
    executionMode: defaultEditorState.executionMode,
    selectedId: typeof candidate.selectedId === "string" ? candidate.selectedId : null,
    activeTab: typeof candidate.activeTab === "string" ? candidate.activeTab : "overview",
    filter: typeof candidate.filter === "string" ? candidate.filter : "",
    errorCode: null,
    contextBinding: restoreContext(candidate.contextBinding),
    visible: typeof candidate.visible === "boolean" ? candidate.visible : true,
  };
}

export function applyServerEditorState(
  local: RenderEditorLocalState,
  server: RenderEditorServerState,
): RenderEditorLocalState {
  if (!statuses.has(server.status) || !modes.has(server.executionMode)) {
    throw new TypeError("server returned an unknown Render Ops state or execution mode");
  }
  return {
    ...local,
    status: server.status,
    executionMode: server.executionMode,
    selectedId: server.selectedId,
    errorCode: server.errorCode,
  };
}
