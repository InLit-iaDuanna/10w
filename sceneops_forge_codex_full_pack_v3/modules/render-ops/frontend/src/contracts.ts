export type ExecutionMode = "live" | "cached" | "mock" | "planned" | "blocked";

export type EditorStatus =
  | "loading"
  | "empty"
  | "ready"
  | "failed"
  | "offline"
  | "permission-denied";

export type ContextBinding =
  | { mode: "follow-global" }
  | {
      mode: "pinned";
      context: {
        projectId?: string;
        sceneId?: string;
        activeRenderJobId?: string;
      };
    };

export interface CommandClient {
  execute(commandId: string, input: Record<string, unknown>): Promise<unknown>;
}

export interface RenderEditorLocalState {
  schemaVersion: 1;
  status: EditorStatus;
  executionMode: ExecutionMode;
  selectedId: string | null;
  activeTab: string;
  filter: string;
  errorCode: string | null;
  contextBinding: ContextBinding;
  visible: boolean;
}

export interface RenderEditorServerState {
  status: EditorStatus;
  executionMode: ExecutionMode;
  selectedId: string | null;
  errorCode: string | null;
}

export interface RenderEditorProps {
  instanceId: string;
  localState: RenderEditorLocalState;
  commands: CommandClient;
  updateLocalState(patch: Partial<RenderEditorLocalState>): void;
}

export interface EditorAction {
  label: string;
  commandId: string;
  input: Record<string, unknown>;
}

export interface EditorPresentation {
  editorId: string;
  title: string;
  stateLabel: string;
  modeLabel: string;
  tone: "neutral" | "info" | "success" | "warning" | "critical";
  message: string;
  actions: EditorAction[];
  sections: Array<{
    title: string;
    rows: Array<{ label: string; value: string }>;
  }>;
  preservesServerQueue: boolean;
  disclaimer?: string;
}

export interface EditorDefinition {
  id: string;
  title: string;
  icon: string;
  category: "render";
  load: () => Promise<unknown>;
  defaultPlacement: "center" | "bottom" | "right";
  minWidth: number;
  minHeight: number;
  singleton: boolean;
  requiredPermissions: string[];
  optionalIntegrations: string[];
  serializeState: (state: RenderEditorLocalState) => unknown;
  restoreState: (value: unknown) => RenderEditorLocalState;
}
