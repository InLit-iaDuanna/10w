import type {
  ExecutionMode,
  PerformanceBudget,
  ProjectIntakeRecord,
} from "../../../project-intake/frontend/src/index.ts";

export type { ExecutionMode, ProjectIntakeRecord };

export type DesignDocumentStatus = "draft" | "in-review" | "approved";

export interface IdentifiedStatement {
  readonly id: string;
  readonly statement: string;
}

export interface AudienceProfile {
  readonly audienceId: string;
  readonly description: string;
  readonly playerNeeds: readonly string[];
}

export interface CoreLoopStep {
  readonly stepId: string;
  readonly order: number;
  readonly action: string;
  readonly feedback: string;
  readonly playerValue: string;
}

export interface DesignRule extends IdentifiedStatement {
  readonly rationale: string;
}

export interface ProhibitedChange extends IdentifiedStatement {
  readonly scope: string;
}

export interface DesignAssumption extends IdentifiedStatement {
  readonly sourceMessageId: string;
  readonly status: "unconfirmed" | "confirmed" | "rejected";
}

export interface ProjectBible {
  readonly schemaVersion: 1;
  readonly documentType: "project-bible";
  readonly bibleId: string;
  readonly projectId: string;
  readonly sourceIntakeId: string;
  readonly title: string;
  readonly status: DesignDocumentStatus;
  readonly gameGoal: string;
  readonly targetPlayers: readonly AudienceProfile[];
  readonly coreLoop: readonly CoreLoopStep[];
  readonly visualRules: readonly DesignRule[];
  readonly audioRules: readonly DesignRule[];
  readonly interactionRules: readonly DesignRule[];
  readonly namingRules: readonly DesignRule[];
  readonly platformBudgets: readonly PerformanceBudget[];
  readonly prohibitedChanges: readonly ProhibitedChange[];
  readonly approvedDecisionIds: readonly string[];
  readonly assumptions: readonly DesignAssumption[];
}

export interface GameplaySystem {
  readonly systemId: string;
  readonly name: string;
  readonly purpose: string;
  readonly inputs: readonly IdentifiedStatement[];
  readonly outputs: readonly IdentifiedStatement[];
  readonly dependencyIds: readonly string[];
  readonly edgeCases: readonly IdentifiedStatement[];
}

export interface GddDocument {
  readonly schemaVersion: 1;
  readonly documentType: "gdd";
  readonly gddId: string;
  readonly projectId: string;
  readonly title: string;
  readonly status: DesignDocumentStatus;
  readonly executiveSummary: string;
  readonly designPillars: readonly IdentifiedStatement[];
  readonly playerExperienceGoals: readonly IdentifiedStatement[];
  readonly gameplaySystems: readonly GameplaySystem[];
  readonly progression: readonly IdentifiedStatement[];
  readonly worldStructure: readonly IdentifiedStatement[];
  readonly economyRules: readonly IdentifiedStatement[];
  readonly failureRecovery: readonly IdentifiedStatement[];
  readonly dependencyIds: readonly string[];
  readonly assumptions: readonly DesignAssumption[];
}

export interface FeatureInput extends IdentifiedStatement {
  readonly source: "player" | "system" | "content";
}

export interface FeatureOutput extends IdentifiedStatement {
  readonly consumer: "player" | "system" | "telemetry";
}

export interface FeatureDependency {
  readonly dependencyId: string;
  readonly kind: "feature" | "system" | "integration" | "decision";
  readonly requiredState: string;
}

export interface FeatureEdgeCase extends IdentifiedStatement {
  readonly expectedBehavior: string;
}

export interface AcceptanceCriterion {
  readonly criterionId: string;
  readonly title: string;
  readonly given: string;
  readonly when: string;
  readonly then: string;
  readonly priority: "must" | "should" | "could";
}

export type DeliverableKind = "asset" | "scene" | "script" | "ui" | "audio" | "vfx";

export interface RequiredDeliverable {
  readonly requirementId: string;
  readonly kind: DeliverableKind;
  readonly description: string;
  readonly existingArtifactId: string | null;
}

export interface RequiredTest {
  readonly testId: string;
  readonly level: "unit" | "integration" | "playtest" | "visual";
  readonly description: string;
  readonly linkedCriterionIds: readonly string[];
}

export interface FeatureSpec {
  readonly schemaVersion: 1;
  readonly documentType: "feature-spec";
  readonly featureSpecId: string;
  readonly projectId: string;
  readonly gddId: string | null;
  readonly title: string;
  readonly status: DesignDocumentStatus | "ready-for-planning";
  readonly goal: string;
  readonly playerValue: string;
  readonly inputs: readonly FeatureInput[];
  readonly outputs: readonly FeatureOutput[];
  readonly dependencies: readonly FeatureDependency[];
  readonly edgeCases: readonly FeatureEdgeCase[];
  readonly acceptanceCriteria: readonly AcceptanceCriterion[];
  readonly requiredDeliverables: readonly RequiredDeliverable[];
  readonly requiredTests: readonly RequiredTest[];
  readonly assumptions: readonly DesignAssumption[];
}

export type VersionedDesignDocument = ProjectBible | FeatureSpec;
export type DesignDocumentType = VersionedDesignDocument["documentType"];

export interface DocumentVersion<TDocument extends VersionedDesignDocument> {
  readonly versionId: string;
  readonly versionNumber: number;
  readonly documentType: TDocument["documentType"];
  readonly documentId: string;
  readonly document: TDocument;
  readonly actorId: string;
  readonly createdAt: string;
  readonly rationale: string;
  readonly mode: ExecutionMode;
  readonly sourceChangeSetId: string | null;
}

export interface StructuralDiffEntry {
  readonly path: string;
  readonly kind: "added" | "removed" | "changed";
  readonly before: unknown;
  readonly after: unknown;
}

export interface DecisionAlternative {
  readonly alternativeId: string;
  readonly title: string;
  readonly consequences: readonly string[];
  readonly disposition: "pending" | "accepted" | "rejected";
  readonly rationale: string | null;
}

export interface DecisionRecord {
  readonly decisionId: string;
  readonly projectId: string;
  readonly subject: string;
  readonly status: "open" | "decided";
  readonly alternatives: readonly DecisionAlternative[];
  readonly decidedBy: string | null;
  readonly decidedAt: string | null;
}

export interface DesignChangeSet<TDocument extends VersionedDesignDocument = VersionedDesignDocument> {
  readonly changeSetId: string;
  readonly targetType: TDocument["documentType"];
  readonly targetId: string;
  readonly baseVersionId: string;
  readonly previousValue: TDocument;
  readonly proposedValue: TDocument;
  readonly rationale: string;
  readonly expectedResult: string;
  readonly impactScope: readonly string[];
  readonly risk: "low" | "medium" | "high";
  readonly validationPlan: readonly string[];
  readonly rollbackPlan: readonly string[];
  readonly approvalRequirements: readonly ["design:approve"];
  readonly source: "assistant";
  readonly status: "waiting-approval" | "approved" | "rejected" | "applied";
  readonly createdBy: string;
  readonly createdAt: string;
  readonly approvedBy: string | null;
  readonly approvedAt: string | null;
}

export interface ConversationFeatureDraftInput {
  readonly featureSpecId: string;
  readonly projectId: string;
  readonly gddId: string | null;
  readonly title: string;
  readonly goal: string;
  readonly playerValue: string;
  readonly inputs: readonly FeatureInput[];
  readonly outputs: readonly FeatureOutput[];
  readonly dependencies: readonly FeatureDependency[];
  readonly edgeCases: readonly FeatureEdgeCase[];
  readonly acceptanceCriteria: readonly AcceptanceCriterion[];
  readonly requiredDeliverables: readonly RequiredDeliverable[];
  readonly requiredTests: readonly RequiredTest[];
  readonly inferredStatements: readonly IdentifiedStatement[];
  readonly sourceMessageId: string;
}

export interface DesignValidationIssue {
  readonly code:
    | "PROJECT_INTAKE_NOT_READY"
    | "MISSING_FEATURE_TITLE"
    | "MISSING_FEATURE_GOAL"
    | "MISSING_INPUT"
    | "MISSING_OUTPUT"
    | "MISSING_ACCEPTANCE_CRITERIA"
    | "INCOMPLETE_ACCEPTANCE_CRITERION"
    | "MISSING_REQUIRED_TEST"
    | "UNCONFIRMED_ASSUMPTION";
  readonly path: string;
  readonly message: string;
}

export interface PlanningReadyPayload {
  readonly featureSpecId: string;
  readonly featureVersionId: string;
  readonly dependencyIds: readonly string[];
  readonly acceptanceCriterionIds: readonly string[];
  readonly requiredDeliverables: readonly {
    readonly requirementId: string;
    readonly kind: DeliverableKind;
  }[];
  readonly requiredTestIds: readonly string[];
}

export interface DocumentVersionedPayload {
  readonly documentType: DesignDocumentType;
  readonly documentId: string;
  readonly versionId: string;
  readonly versionNumber: number;
}

export interface DecisionRecordedPayload {
  readonly decisionId: string;
  readonly status: DecisionRecord["status"];
  readonly acceptedAlternativeId: string | null;
}

export interface DesignEventEnvelope<TPayload> {
  readonly eventId: string;
  readonly eventType:
    | "design.project_bible.versioned"
    | "design.feature_spec.versioned"
    | "design.feature_spec.marked_ready"
    | "design.decision.recorded";
  readonly eventVersion: 1;
  readonly occurredAt: string;
  readonly projectId: string;
  readonly correlationId: string;
  readonly causationId: string;
  readonly actor: { readonly type: "user" | "assistant"; readonly id: string };
  readonly mode: ExecutionMode;
  readonly payload: TPayload;
}

export interface DesignCommandMetadata {
  readonly commandId: string;
  readonly eventId: string;
  readonly correlationId: string;
  readonly actorId: string;
  readonly actorType: "user" | "assistant";
  readonly occurredAt: string;
  readonly mode: ExecutionMode;
}

export interface DesignCommandContext {
  readonly moduleEnabled: boolean;
  readonly permissions: ReadonlySet<string>;
}

export interface DesignCommandAvailability {
  readonly available: boolean;
  readonly code: "AVAILABLE" | "MODULE_DISABLED" | "PERMISSION_DENIED";
  readonly message: string;
}

export interface DesignOpenEditorAction {
  readonly type: "workbench.open_editor";
  readonly editorId: "design.feature_spec";
  readonly placement: { readonly mode: "tab" };
  readonly context: { readonly projectId: string; readonly activeFeatureId: string };
  readonly requireConfirmation: false;
}

export class DesignRoomError extends Error {
  readonly code:
    | "MODULE_DISABLED"
    | "PERMISSION_DENIED"
    | "INVALID_ACTOR"
    | "INVALID_CHANGESET"
    | "DOCUMENT_NOT_FOUND"
    | "VERSION_NOT_FOUND"
    | "VERSION_ID_CONFLICT"
    | "CHANGESET_NOT_FOUND"
    | "CHANGESET_NOT_APPROVABLE"
    | "BASE_VERSION_CONFLICT"
    | "DESIGN_NOT_ACTIONABLE"
    | "DECISION_NOT_FOUND"
    | "ALTERNATIVE_NOT_FOUND"
    | "INVALID_DECISION_RATIONALE"
    | "DECISION_ALREADY_FINAL"
    | "PENDING_ALTERNATIVES";
  readonly details: Readonly<Record<string, unknown>>;

  constructor(
    code: DesignRoomError["code"],
    message: string,
    details: Readonly<Record<string, unknown>> = {},
  ) {
    super(message);
    this.name = "DesignRoomError";
    this.code = code;
    this.details = details;
  }
}
