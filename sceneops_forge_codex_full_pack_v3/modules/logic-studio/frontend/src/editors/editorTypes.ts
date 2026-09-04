export type ExecutionMode = "live" | "cached" | "mock" | "planned" | "blocked";

export type LogicEditorStatus =
  | "loading"
  | "empty"
  | "ready"
  | "failed"
  | "offline"
  | "permission_denied";

export type LogicEditorId =
  | "logic.feature"
  | "logic.state_graph"
  | "logic.interaction_graph"
  | "logic.quest_dialogue"
  | "logic.code_diff"
  | "logic.test_cases";

export type LogicContext = {
  projectId?: string;
  sceneId?: string;
  activeFeatureId?: string;
  activeChangeSetId?: string;
  selectedSceneObjectIds?: string[];
};

export type ContextBinding =
  | { mode: "follow-global" }
  | { mode: "pinned"; context: LogicContext };

export type LogicEditorState = {
  schemaVersion: 1;
  status: LogicEditorStatus;
  mode: ExecutionMode;
  contextBinding: ContextBinding;
  selectedEntityIds: string[];
  errorCode?: string;
};

export type LogicEditorAction = {
  id: "retry" | "open_integration" | "request_permission";
  label: string;
};

export type LogicEditorView = {
  editorId: LogicEditorId;
  title: string;
  status: LogicEditorStatus;
  statusLabel: string;
  modeLabel: string;
  tone: "neutral" | "success" | "warning" | "critical";
  message: string;
  actions: LogicEditorAction[];
};

export type LogicEditorDefinition = {
  id: LogicEditorId;
  title: string;
  icon: string;
  category: "logic";
  defaultPlacement: "center" | "right" | "bottom";
  minWidth: number;
  minHeight: number;
  singleton: boolean;
  requiredPermissions: string[];
  optionalIntegrations: string[];
  supportsContextBinding: true;
  emptyMessage: string;
  load: () => Promise<{ default: LogicEditorRuntime }>;
  serializeState: (state: LogicEditorState) => Record<string, unknown>;
  restoreState: (value: unknown) => LogicEditorState;
};

export type LogicEditorRuntime = {
  createView: (
    definition: LogicEditorDefinition,
    state: LogicEditorState,
  ) => LogicEditorView;
};
