export type ExecutionMode = "live" | "cached" | "mock" | "planned" | "blocked";
export type LogLevel = "trace" | "debug" | "info" | "warning" | "error" | "critical";
export type EditorPhase = "loading" | "empty" | "ready" | "failed" | "disconnected" | "permission_denied";

export interface CorrelationContextView {
  projectId: string;
  runId?: string;
  jobId?: string;
  correlationId: string;
  causationId: string;
}

export interface ArtifactLinkView {
  artifactId: string;
  label: string;
  mediaType?: string;
}

export interface StructuredLogView {
  eventId: string;
  emittedAt: string;
  level: LogLevel;
  sourceModule: string;
  sourceTool?: string;
  workerId?: string;
  message: string;
  context: CorrelationContextView;
  fields: Record<string, string | number | boolean | null>;
  artifactLinks: ArtifactLinkView[];
  mode: ExecutionMode;
}

export interface LogFilterState {
  text: string;
  minimumLevel?: LogLevel;
  sourceModule?: string;
  sourceTool?: string;
  runId?: string;
  jobId?: string;
  correlationId?: string;
  fieldEquals?: Record<string, string | number | boolean | null>;
}

export interface LogExplorerState {
  phase: EditorPhase;
  filters: LogFilterState;
  items: StructuredLogView[];
  errorMessage?: string;
  canExportDiagnostics: boolean;
  exportUnavailableReason?: string;
}

export interface EditorActionView {
  commandId: string;
  label: string;
  available: boolean;
  unavailableReason?: string;
}

export interface LogRowView {
  id: string;
  primary: string;
  secondary: string;
  level: LogLevel;
  modeLabel: string;
  correlationLabel: string;
  fields: string[];
  artifacts: ArtifactLinkView[];
}

export interface LogExplorerView {
  editorId: "observability.logs";
  title: string;
  status: EditorPhase;
  banner: string;
  rows: LogRowView[];
  actions: EditorActionView[];
  selectableText: boolean;
}
