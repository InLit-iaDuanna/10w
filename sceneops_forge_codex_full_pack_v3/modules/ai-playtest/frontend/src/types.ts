import type { ZodSchema } from "zod";

export type ExecutionMode = "live" | "cached" | "mock" | "planned" | "blocked";

export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

export type EditorSurfaceState =
  | "loading"
  | "empty"
  | "ready"
  | "failed"
  | "offline"
  | "permission_denied"
  | "disabled";

export interface CameraPose {
  position: [number, number, number];
  rotationEulerDegrees: [number, number, number];
}

export interface WorkbenchContext {
  projectId: string | null;
  branchId: string | null;
  sceneId: string | null;
  selectedSceneObjectIds: string[];
  selectedAssetIds: string[];
  activeFeatureId: string | null;
  activeTaskId: string | null;
  activeChangeSetId: string | null;
  activeRenderJobId: string | null;
  activeBuildId: string | null;
  activePlaytestRunId: string | null;
  activeIssueId: string | null;
  cameraPose?: CameraPose;
  timelineTime?: number;
}

export type ContextBinding =
  | { mode: "follow-global" }
  | { mode: "pinned"; context: Partial<WorkbenchContext> };

export interface WorkbenchCommandClient {
  execute<TResult = unknown>(commandId: string, input: unknown): Promise<TResult>;
}

export interface WorkbenchEventClient {
  publish(eventType: string, payload: JsonValue): Promise<void>;
}

export interface EditorProps<TState> {
  instanceId: string;
  contextBinding: ContextBinding;
  localState: TState;
  updateLocalState: (patch: Partial<TState>) => void;
  commands: WorkbenchCommandClient;
  events: WorkbenchEventClient;
  close: () => void;
  setTitle: (title: string) => void;
}

export interface GoalProgressView {
  goalId: string;
  label: string;
  state: "pending" | "in_progress" | "completed" | "blocked";
  value: number;
}

export interface StepView {
  stepIndex: number;
  occurredAt: string;
  actionId: string;
  actionLabel: string;
  outcome: "succeeded" | "failed" | "timed_out" | "cancelled";
  targetSceneOpsId?: string;
  position: [number, number, number];
  camera: CameraPose;
  gameState: { [key: string]: JsonValue };
  goals: GoalProgressView[];
  availableActionIds: string[];
  evidenceArtifactIds: string[];
  signalKinds: string[];
}

export interface IssueView {
  issueId: string;
  title: string;
  severity: "info" | "warning" | "error" | "critical";
  failureKind: string;
  backpinStatus: "resolved" | "ambiguous" | "unresolved" | "rejected";
  backpinConfidence: number;
  backpinTargetId?: string;
  backpinReasons: string[];
  backpinAlternatives: string[];
  backpinReviewedBy?: string;
  stepIndex?: number;
  limitationLabels: string[];
}

export interface RegressionMetricView {
  metricId: string;
  baseline?: number;
  candidate?: number;
  outcome: "improved" | "regressed" | "unchanged" | "missing";
  unit: string;
}

export interface PlaytestReadModel {
  surfaceState: EditorSurfaceState;
  executionMode: ExecutionMode;
  runId?: string;
  status?: "queued" | "running" | "succeeded" | "failed" | "cancelled" | "blocked";
  objective?: string;
  agentMode?: "smoke" | "goal_driven" | "explorer" | "destructive" | "persona";
  actionBounds?: {
    maxSteps: number;
    maxDurationMs: number;
    actionTimeoutMs: number;
  };
  buildId?: string;
  screenshotUri?: string;
  camera?: CameraPose;
  goals: GoalProgressView[];
  steps: StepView[];
  issues: IssueView[];
  regressionStatus?: "improved" | "regressed" | "unchanged" | "mixed" | "incomparable";
  exactConfiguration?: boolean;
  baselineBuildId?: string;
  candidateBuildId?: string;
  newIssueIds: string[];
  resolvedIssueIds: string[];
  persistentIssueIds: string[];
  regressionMetrics: RegressionMetricView[];
  limitationLabels: string[];
  summary?: string;
  errorMessage?: string;
}

export interface PlaytestEditorState {
  followLatest: boolean;
  selectedStepIndex?: number;
  selectedIssueId?: string;
  trajectoryZoom: number;
  comparisonId?: string;
  baselineRunId?: string;
  candidateRunId?: string;
}

export interface PlaytestEditorProps extends EditorProps<PlaytestEditorState> {
  readModel: PlaytestReadModel;
  retryInput?: unknown;
}

export type EditorComponent<TProps> = (props: TProps) => unknown;

export interface EditorDefinition<TState, TProps extends EditorProps<TState>> {
  id: string;
  title: string;
  icon: string;
  category: "test";
  load: () => Promise<{ default: EditorComponent<TProps> }>;
  defaultPlacement: "center" | "right" | "bottom";
  minWidth?: number;
  minHeight?: number;
  singleton?: boolean;
  requiredPermissions?: string[];
  requiredIntegrations?: string[];
  optionalIntegrations?: string[];
  serializeState: (state: TState) => JsonValue;
  restoreState: (value: JsonValue) => TState;
  supportsContextBinding: true;
  supportedStates: EditorSurfaceState[];
}

export interface CommandAvailabilityContext extends WorkbenchContext {
  moduleEnabled: boolean;
  grantedPermissions: string[];
  requestedMode: ExecutionMode;
  playtestRunnerAvailable: boolean;
  cachedPlaytestAvailable: boolean;
}

export interface CommandAvailability {
  available: boolean;
  code?:
    | "MODULE_DISABLED"
    | "PERMISSION_DENIED"
    | "INTEGRATION_OFFLINE"
    | "CACHED_RESULT_UNAVAILABLE"
    | "INVALID_CONTEXT";
  message?: string;
}

export interface CommandExecutionContext {
  playtestApi: PlaytestCommandApi;
}

export interface RunPlaytestInput {
  runId: string;
  testCaseId: string;
  buildId: string;
  executionMode: ExecutionMode;
  replayActionIds: string[];
}

export interface CancelPlaytestInput {
  runId: string;
}

export interface OpenIssueBackpinInput {
  issueId: string;
}

export interface ProposeIssueChangeInput {
  issueId: string;
}

export interface ReviewBackpinInput {
  issueId: string;
  decision: "confirm" | "reject";
}

export interface CompareRegressionInput {
  comparisonId: string;
  baselineRunId: string;
  candidateRunId: string;
}

export interface PlaytestCommandApi {
  run(input: RunPlaytestInput): Promise<unknown>;
  cancel(input: CancelPlaytestInput): Promise<unknown>;
  restoreIssue(input: OpenIssueBackpinInput): Promise<unknown>;
  beginChangeProposal(input: ProposeIssueChangeInput): Promise<unknown>;
  reviewBackpin(input: ReviewBackpinInput): Promise<unknown>;
  compare(input: CompareRegressionInput): Promise<unknown>;
}

export interface WorkbenchCommandDefinition<TInput, TResult> {
  id: string;
  title: string;
  inputSchema: ZodSchema<TInput>;
  requiredPermissions: string[];
  requiredIntegrations?: string[];
  canExecute(
    context: CommandAvailabilityContext,
    input: TInput,
  ): CommandAvailability;
  execute(context: CommandExecutionContext, input: TInput): Promise<TResult>;
}
