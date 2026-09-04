export type ExecutionMode = "live" | "cached" | "mock" | "planned" | "blocked";
export type HealthSummaryState =
  | "connected"
  | "disconnected"
  | "degraded"
  | "incompatible"
  | "busy"
  | "unauthorized"
  | "unknown";
export type EditorPhase = "loading" | "empty" | "ready" | "failed" | "disconnected" | "permission_denied";
export type JobState =
  | "queued"
  | "running"
  | "paused"
  | "failed"
  | "timed_out"
  | "cancel_requested"
  | "cancelled"
  | "succeeded";

export interface RecommendedActionView {
  commandId: string;
  label: string;
  available: boolean;
  unavailableReason?: string;
}

export interface JobView {
  jobId: string;
  runId: string;
  correlationId: string;
  title: string;
  state: JobState;
  progress: number;
  retrySafety: "idempotent" | "compensated" | "non_idempotent";
  resumeTokenAvailable: boolean;
  completedStepIds: string[];
}

export interface RecoveryResultView {
  jobId: string;
  integrationId: string;
  operationId: string;
  attemptId: string;
  action: "timeout" | "cancel" | "retry" | "resume";
  state: JobState;
  completedStepIds: string[];
  idempotencyKey: string;
  duplicate: boolean;
  reconciliation: string;
  message: string;
  mode: ExecutionMode;
  context: {
    projectId: string;
    runId?: string;
    jobId?: string;
    correlationId: string;
    causationId: string;
  };
}

export interface QueueView {
  depth: number;
  running: number;
  oldestQueuedAt?: string;
}

export interface IntegrationHealthView {
  integrationId: string;
  displayName: string;
  state: HealthSummaryState;
  toolVersion?: string;
  adapterVersion?: string;
  capabilityIds: string[];
  lastSeenAt?: string;
  currentJob?: JobView;
  queue: QueueView;
  reason?: string;
  mode: ExecutionMode;
  isCurrent: boolean;
  liveActionsEnabled: boolean;
  recommendedActions: RecommendedActionView[];
}

export interface LogSummaryView {
  eventId: string;
  integrationId: string;
  level: "trace" | "debug" | "info" | "warning" | "error" | "critical";
  message: string;
  correlationId: string;
  artifactIds: string[];
  mode: ExecutionMode;
}

export interface WorkerView {
  workerId: string;
  integrationId: string;
  displayName: string;
  lifecycle: "online" | "offline" | "draining" | "unknown";
  healthState: HealthSummaryState;
  observedAt: string;
  expiresAt: string;
  isCurrent: boolean;
  lastHeartbeatAt?: string;
  workerVersion: string;
  capabilityIds: string[];
  currentJob?: JobView;
  queue: QueueView;
  mode: ExecutionMode;
  recommendedActions: RecommendedActionView[];
}

export interface IntegrationHealthEditorState {
  phase: EditorPhase;
  integrations: IntegrationHealthView[];
  recentLogs: LogSummaryView[];
  selectedIntegrationId?: string;
  searchText: string;
  errorMessage?: string;
}

export interface WorkerMonitorEditorState {
  phase: EditorPhase;
  workers: WorkerView[];
  recentLogs: LogSummaryView[];
  selectedWorkerId?: string;
  searchText: string;
  errorMessage?: string;
}

export interface HealthRowView {
  id: string;
  name: string;
  state: HealthSummaryState;
  stateLabel: string;
  modeLabel: string;
  versionLabel: string;
  capabilityLabel: string;
  lastSeenLabel: string;
  jobLabel: string;
  queueLabel: string;
  explanation: string;
  actions: RecommendedActionView[];
  logs: LogSummaryView[];
}

export interface WorkerRowView {
  id: string;
  name: string;
  lifecycleLabel: string;
  stateLabel: string;
  modeLabel: string;
  versionLabel: string;
  capabilityLabel: string;
  freshnessLabel: string;
  heartbeatLabel: string;
  jobLabel: string;
  queueLabel: string;
  actions: RecommendedActionView[];
  recoveryActions: RecommendedActionView[];
  logs: LogSummaryView[];
}

export interface IntegrationHealthEditorView {
  editorId: "integration.health";
  title: string;
  status: EditorPhase;
  banner: string;
  rows: HealthRowView[];
}

export interface WorkerMonitorEditorView {
  editorId: "worker.monitor";
  title: string;
  status: EditorPhase;
  banner: string;
  rows: WorkerRowView[];
}
