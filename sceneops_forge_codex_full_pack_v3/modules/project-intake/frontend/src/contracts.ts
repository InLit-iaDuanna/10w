export type ExecutionMode = "live" | "cached" | "mock" | "planned" | "blocked";

export type FieldConfidence = "confirmed" | "inferred" | "missing";

export type FieldOrigin = "user" | "conversation" | "project-scan" | "none";

export interface FieldEvidence {
  readonly origin: FieldOrigin;
  readonly reference: string;
  readonly observedAt: string;
}

export interface TrackedField<T> {
  readonly value: T | null;
  readonly confidence: FieldConfidence;
  readonly evidence: FieldEvidence | null;
}

export interface ToolSelection {
  readonly toolId: string;
  readonly displayName: string;
  readonly version: string | null;
}

export interface ProjectRoot {
  readonly rootId: string;
  readonly kind: "workspace" | "engine-project" | "dcc-project";
  readonly absolutePath: string;
  readonly displayName: string;
}

export interface TeamRole {
  readonly roleId: string;
  readonly title: string;
  readonly responsibilities: readonly string[];
  readonly assigneeId: string | null;
}

export interface StyleGoal {
  readonly goalId: string;
  readonly dimension: "visual" | "audio" | "interaction" | "narrative";
  readonly statement: string;
  readonly references: readonly string[];
}

export interface PerformanceBudget {
  readonly budgetId: string;
  readonly platform: string;
  readonly metric: string;
  readonly limit: number;
  readonly unit: string;
  readonly measurementContext: string;
}

export interface IntegrationRequirement {
  readonly integrationId: string;
  readonly capability: string;
  readonly required: boolean;
  readonly notes: string;
}

export interface ProjectIntakeValues {
  readonly projectName: string;
  readonly targetPlatforms: readonly string[];
  readonly engine: ToolSelection;
  readonly dccs: readonly ToolSelection[];
  readonly projectRoots: readonly ProjectRoot[];
  readonly teamRoles: readonly TeamRole[];
  readonly styleGoals: readonly StyleGoal[];
  readonly performanceBudgets: readonly PerformanceBudget[];
  readonly integrationRequirements: readonly IntegrationRequirement[];
}

export type IntakeFieldKey = keyof ProjectIntakeValues;

export type ProjectIntakeFields = {
  readonly [K in IntakeFieldKey]: TrackedField<ProjectIntakeValues[K]>;
};

export interface ProjectScanReference {
  readonly adapterId: string;
  readonly adapterVersion: string;
  readonly scanId: string;
  readonly scannedAt: string;
  readonly mode: ExecutionMode;
  readonly warnings: readonly string[];
}

export interface ProjectIntakeRecord {
  readonly schemaVersion: 1;
  readonly intakeId: string;
  readonly projectId: string;
  readonly kind: "new-project" | "existing-project";
  readonly status: "draft" | "needs-confirmation" | "ready";
  readonly fields: ProjectIntakeFields;
  readonly scanReference: ProjectScanReference | null;
  readonly mode: ExecutionMode;
  readonly createdAt: string;
  readonly updatedAt: string;
}

export interface NewProjectIntakeInput {
  readonly intakeId: string;
  readonly projectId: string;
  readonly projectName?: string;
  readonly targetPlatforms?: readonly string[];
  readonly engine?: ToolSelection;
  readonly dccs?: readonly ToolSelection[];
  readonly projectRoots?: readonly ProjectRoot[];
  readonly teamRoles?: readonly TeamRole[];
  readonly styleGoals?: readonly StyleGoal[];
  readonly performanceBudgets?: readonly PerformanceBudget[];
  readonly integrationRequirements?: readonly IntegrationRequirement[];
  readonly actorId: string;
  readonly occurredAt: string;
  readonly mode: ExecutionMode;
}

export interface ConversationProjectIntent extends NewProjectIntakeInput {
  readonly sourceMessageId: string;
}

export interface ExistingProjectScanInput {
  readonly intakeId: string;
  readonly projectId: string;
  readonly projectRoot: ProjectRoot | null;
  readonly adapterId: string;
  readonly actorId: string;
  readonly occurredAt: string;
}

export interface IntakeValidationIssue {
  readonly code:
    | "MISSING_PROJECT_NAME"
    | "MISSING_TARGET_PLATFORM"
    | "MISSING_PROJECT_ROOT"
    | "INVALID_PROJECT_ROOT"
    | "TARGET_PLATFORM_NOT_CONFIRMED"
    | "PROJECT_ROOT_NOT_CONFIRMED";
  readonly field: IntakeFieldKey;
  readonly message: string;
}

export interface WorkbenchOpenEditorAction {
  readonly type: "workbench.open_editor";
  readonly editorId: "project.intake";
  readonly placement: {
    readonly mode: "tab";
  };
  readonly context: {
    readonly projectId: string;
  };
  readonly requireConfirmation: false;
}

export interface CommandMetadata {
  readonly commandId: string;
  readonly eventId: string;
  readonly correlationId: string;
  readonly actorId: string;
  readonly occurredAt: string;
}

export interface IntakeEventEnvelope<TPayload> {
  readonly eventId: string;
  readonly eventType: "project.intake.drafted" | "project.intake.field_confirmed";
  readonly eventVersion: 1;
  readonly occurredAt: string;
  readonly projectId: string;
  readonly correlationId: string;
  readonly causationId: string;
  readonly actor: {
    readonly type: "user" | "assistant";
    readonly id: string;
  };
  readonly mode: ExecutionMode;
  readonly payload: TPayload;
}

export interface IntakeDraftedPayload {
  readonly intakeId: string;
  readonly kind: ProjectIntakeRecord["kind"];
  readonly status: ProjectIntakeRecord["status"];
  readonly inferredFields: readonly IntakeFieldKey[];
  readonly missingFields: readonly IntakeFieldKey[];
}

export interface IntakeFieldConfirmedPayload {
  readonly intakeId: string;
  readonly field: IntakeFieldKey;
  readonly status: ProjectIntakeRecord["status"];
}

export type ProjectIntakeEvent =
  | IntakeEventEnvelope<IntakeDraftedPayload>
  | IntakeEventEnvelope<IntakeFieldConfirmedPayload>;

export interface CommandAvailability {
  readonly available: boolean;
  readonly code: "AVAILABLE" | "MODULE_DISABLED" | "PERMISSION_DENIED";
  readonly message: string;
}

export interface ProjectIntakeCommandContext {
  readonly moduleEnabled: boolean;
  readonly permissions: ReadonlySet<string>;
}

export class ProjectIntakeError extends Error {
  readonly code:
    | "MODULE_DISABLED"
    | "PERMISSION_DENIED"
    | "INTEGRATION_OFFLINE"
    | "INTEGRATION_PERMISSION_DENIED"
    | "MISSING_PROJECT_ROOT"
    | "INVALID_PROJECT_ROOT"
    | "ADAPTER_NOT_FOUND"
    | "INTAKE_NOT_FOUND"
    | "SCAN_CANCELLED"
    | "SCAN_FAILED";
  readonly retryable: boolean;
  readonly suggestedActions: readonly string[];

  constructor(
    code: ProjectIntakeError["code"],
    message: string,
    retryable: boolean,
    suggestedActions: readonly string[],
  ) {
    super(message);
    this.name = "ProjectIntakeError";
    this.code = code;
    this.retryable = retryable;
    this.suggestedActions = suggestedActions;
  }
}
