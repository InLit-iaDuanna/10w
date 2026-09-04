import type { IntegrationHealthEditorState, WorkerMonitorEditorState } from "./types.ts";
import { integrationCenterCommands } from "./commands.ts";

export interface EditorDefinition<State> {
  id: string;
  title: string;
  icon: string;
  category: "system";
  load: () => Promise<{ default: (state: State) => unknown }>;
  defaultPlacement: "right" | "bottom";
  minWidth: number;
  minHeight: number;
  singleton: boolean;
  requiredPermissions: string[];
  optionalIntegrations: string[];
  serializeState: (state: State) => unknown;
  restoreState: (value: unknown) => State;
}

export const defaultHealthEditorState: IntegrationHealthEditorState = {
  phase: "loading",
  integrations: [],
  recentLogs: [],
  searchText: "",
};

export const defaultWorkerEditorState: WorkerMonitorEditorState = {
  phase: "loading",
  workers: [],
  recentLogs: [],
  searchText: "",
};

function restoreHealth(value: unknown): IntegrationHealthEditorState {
  if (!value || typeof value !== "object") return defaultHealthEditorState;
  const candidate = value as Partial<IntegrationHealthEditorState>;
  return {
    ...defaultHealthEditorState,
    selectedIntegrationId:
      typeof candidate.selectedIntegrationId === "string" ? candidate.selectedIntegrationId : undefined,
    searchText: typeof candidate.searchText === "string" ? candidate.searchText : "",
  };
}

function restoreWorkers(value: unknown): WorkerMonitorEditorState {
  if (!value || typeof value !== "object") return defaultWorkerEditorState;
  const candidate = value as Partial<WorkerMonitorEditorState>;
  return {
    ...defaultWorkerEditorState,
    selectedWorkerId: typeof candidate.selectedWorkerId === "string" ? candidate.selectedWorkerId : undefined,
    searchText: typeof candidate.searchText === "string" ? candidate.searchText : "",
  };
}

const optionalIntegrations = ["blender", "unity", "comfyui", "git", "artifact-store"];

export const integrationHealthEditor: EditorDefinition<IntegrationHealthEditorState> = {
  id: "integration.health",
  title: "集成健康",
  icon: "linked-dot",
  category: "system",
  load: () => import("./editors/IntegrationHealthEditor.ts"),
  defaultPlacement: "right",
  minWidth: 420,
  minHeight: 280,
  singleton: true,
  requiredPermissions: ["integration:read"],
  optionalIntegrations,
  serializeState: (state) => ({
    selectedIntegrationId: state.selectedIntegrationId,
    searchText: state.searchText,
  }),
  restoreState: restoreHealth,
};

export const workerMonitorEditor: EditorDefinition<WorkerMonitorEditorState> = {
  id: "worker.monitor",
  title: "Worker 监控",
  icon: "activity",
  category: "system",
  load: () => import("./editors/WorkerMonitorEditor.ts"),
  defaultPlacement: "bottom",
  minWidth: 560,
  minHeight: 260,
  singleton: true,
  requiredPermissions: ["integration:read", "job:read"],
  optionalIntegrations,
  serializeState: (state) => ({ selectedWorkerId: state.selectedWorkerId, searchText: state.searchText }),
  restoreState: restoreWorkers,
};

export const moduleContribution = {
  manifest: {
    id: "integration-center",
    version: "0.1.0",
    featureFlag: "integration_center",
  },
  editors: [integrationHealthEditor, workerMonitorEditor],
  commands: integrationCenterCommands,
} as const;
