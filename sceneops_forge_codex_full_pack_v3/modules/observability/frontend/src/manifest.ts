import type { LogExplorerState } from "./types.ts";
import { observabilityCommands } from "./commands.ts";

export interface EditorDefinition<State> {
  id: string;
  title: string;
  icon: string;
  category: "system";
  load: () => Promise<{ default: (state: State) => unknown }>;
  defaultPlacement: "bottom";
  minWidth: number;
  minHeight: number;
  singleton: boolean;
  requiredPermissions: string[];
  serializeState: (state: State) => unknown;
  restoreState: (value: unknown) => State;
}

export const defaultLogExplorerState: LogExplorerState = {
  phase: "loading",
  filters: { text: "" },
  items: [],
  canExportDiagnostics: false,
  exportUnavailableReason: "权限与项目上下文尚未解析。",
};

function restoreLogExplorerState(value: unknown): LogExplorerState {
  if (!value || typeof value !== "object") return defaultLogExplorerState;
  const candidate = value as Partial<LogExplorerState>;
  if (!candidate.filters || typeof candidate.filters.text !== "string") return defaultLogExplorerState;
  return {
    ...defaultLogExplorerState,
    filters: candidate.filters,
  };
}

export const logExplorerEditor: EditorDefinition<LogExplorerState> = {
  id: "observability.logs",
  title: "日志与追踪",
  icon: "terminal",
  category: "system",
  load: () => import("./editors/LogExplorerEditor.ts"),
  defaultPlacement: "bottom",
  minWidth: 520,
  minHeight: 240,
  singleton: true,
  requiredPermissions: ["observability:read"],
  serializeState: (state) => ({ filters: state.filters }),
  restoreState: restoreLogExplorerState,
};

export const moduleContribution = {
  manifest: {
    id: "observability",
    version: "0.1.0",
    featureFlag: "observability",
  },
  editors: [logExplorerEditor],
  commands: observabilityCommands,
} as const;
