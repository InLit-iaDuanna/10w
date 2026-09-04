export type ExecutionMode = "live" | "cached" | "mock" | "planned" | "blocked";

export type UnityEditorStateKind =
  | "loading"
  | "empty"
  | "ready"
  | "offline"
  | "permission-denied"
  | "failed";

export interface UnityEditorState {
  kind: UnityEditorStateKind;
  mode: ExecutionMode;
  title: string;
  message: string;
  retryCommandId?: string;
  details?: Readonly<Record<string, unknown>>;
}
export interface SerializedUnityEditorState {
  schemaVersion: 1;
  selectedBuildId: string | null;
  selectedSceneOpsId: string | null;
  followGlobalContext: boolean;
  logLevel: "info" | "warning" | "error";
}

export interface UnityEditorDefinition {
  id: string;
  title: string;
  icon: "unity" | "prefab" | "build" | "console" | "profiler";
  category: "engine";
  defaultPlacement: "right" | "bottom" | "center";
  minWidth: number;
  minHeight: number;
  singleton: boolean;
  requiredPermissions: readonly string[];
  requiredIntegrations: readonly ["unity"];
  load: () => Promise<unknown>;
  serializeState: (state: SerializedUnityEditorState) => SerializedUnityEditorState;
  restoreState: (value: unknown) => SerializedUnityEditorState;
}

export interface UnityCommandDefinition {
  id: string;
  title: string;
  requiredPermissions: readonly string[];
  requiredIntegrations: readonly ["unity"];
  mutating: boolean;
  approvalRequired: boolean;
}
