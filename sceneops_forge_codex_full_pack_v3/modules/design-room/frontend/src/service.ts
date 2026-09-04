import type {
  ConversationFeatureDraftInput,
  DecisionRecord,
  DesignChangeSet,
  DesignCommandMetadata,
  DocumentVersion,
  FeatureSpec,
  GddDocument,
  ProjectBible,
  ProjectIntakeRecord,
  StructuralDiffEntry,
  VersionedDesignDocument,
} from "./contracts.ts";
import { DesignRoomError } from "./contracts.ts";
import { acceptDecisionAlternative, rejectDecisionAlternative } from "./decisions.ts";
import { designDocumentId, InMemoryDesignDocumentRepository } from "./repository.ts";
import { validateFeatureForPlanning } from "./validation.ts";

export interface SaveDocumentRequest<TDocument extends VersionedDesignDocument> {
  readonly versionId: string;
  readonly document: TDocument;
  readonly rationale: string;
}

export interface ProposeDesignChangeRequest<TDocument extends VersionedDesignDocument> {
  readonly changeSetId: string;
  readonly baseVersionId: string;
  readonly proposedValue: TDocument;
  readonly rationale: string;
  readonly expectedResult: string;
  readonly impactScope: readonly string[];
  readonly risk: DesignChangeSet["risk"];
  readonly validationPlan: readonly string[];
  readonly rollbackPlan: readonly string[];
}

export interface AppliedDesignChange<TDocument extends VersionedDesignDocument> {
  readonly changeSet: DesignChangeSet<TDocument>;
  readonly version: DocumentVersion<TDocument>;
}

function createConversationFeature(input: ConversationFeatureDraftInput): FeatureSpec {
  return {
    schemaVersion: 1,
    documentType: "feature-spec",
    featureSpecId: input.featureSpecId,
    projectId: input.projectId,
    gddId: input.gddId,
    title: input.title,
    status: "draft",
    goal: input.goal,
    playerValue: input.playerValue,
    inputs: input.inputs,
    outputs: input.outputs,
    dependencies: input.dependencies,
    edgeCases: input.edgeCases,
    acceptanceCriteria: input.acceptanceCriteria,
    requiredDeliverables: input.requiredDeliverables,
    requiredTests: input.requiredTests,
    assumptions: input.inferredStatements.map((statement) => ({
      ...statement,
      sourceMessageId: input.sourceMessageId,
      status: "unconfirmed",
    })),
  };
}

export class DesignRoomService {
  readonly #repository: InMemoryDesignDocumentRepository;

  constructor(repository: InMemoryDesignDocumentRepository) {
    this.#repository = repository;
  }

  saveBible(
    request: SaveDocumentRequest<ProjectBible>,
    metadata: DesignCommandMetadata,
  ): DocumentVersion<ProjectBible> {
    return this.#repository.saveVersion({
      ...request,
      actorId: metadata.actorId,
      createdAt: metadata.occurredAt,
      mode: metadata.mode,
      sourceChangeSetId: null,
    });
  }

  saveFeature(
    request: SaveDocumentRequest<FeatureSpec>,
    metadata: DesignCommandMetadata,
  ): DocumentVersion<FeatureSpec> {
    return this.#repository.saveVersion({
      ...request,
      actorId: metadata.actorId,
      createdAt: metadata.occurredAt,
      mode: metadata.mode,
      sourceChangeSetId: null,
    });
  }

  draftFeatureFromConversation(
    input: ConversationFeatureDraftInput,
    versionId: string,
    metadata: DesignCommandMetadata,
  ): DocumentVersion<FeatureSpec> {
    return this.saveFeature(
      { versionId, document: createConversationFeature(input), rationale: "从对话生成结构化草稿。" },
      metadata,
    );
  }

  saveGdd(document: GddDocument): GddDocument {
    this.#repository.saveGdd(document);
    return document;
  }

  diff(
    documentType: VersionedDesignDocument["documentType"],
    documentId: string,
    fromVersionId: string,
    toVersionId: string,
  ): readonly StructuralDiffEntry[] {
    return this.#repository.diff(documentType, documentId, fromVersionId, toVersionId);
  }

  proposeChange<TDocument extends VersionedDesignDocument>(
    request: ProposeDesignChangeRequest<TDocument>,
    metadata: DesignCommandMetadata,
  ): DesignChangeSet<TDocument> {
    const targetId = designDocumentId(request.proposedValue);
    const latest = this.#repository.latest<TDocument>(request.proposedValue.documentType, targetId);
    if (latest === null) {
      throw new DesignRoomError("DOCUMENT_NOT_FOUND", "找不到 AI 建议的目标文档。", { targetId });
    }
    if (latest.versionId !== request.baseVersionId) {
      throw new DesignRoomError("BASE_VERSION_CONFLICT", "AI 建议的 base version 已过期。", {
        expected: latest.versionId,
        actual: request.baseVersionId,
      });
    }
    const promotesFeatureWithoutReadiness =
      request.proposedValue.documentType === "feature-spec" &&
      request.proposedValue.status === "ready-for-planning" &&
      latest.document.documentType === "feature-spec" &&
      latest.document.status !== "ready-for-planning";
    const missingPlan = request.validationPlan.length === 0 || request.rollbackPlan.length === 0;
    const changedProject = latest.document.projectId !== request.proposedValue.projectId;
    if (promotesFeatureWithoutReadiness || missingPlan || changedProject || request.rationale.trim().length === 0) {
      throw new DesignRoomError("INVALID_CHANGESET", "Design ChangeSet 缺少必要计划或尝试绕过项目/准备度边界。", {
        promotesFeatureWithoutReadiness,
        missingPlan,
        changedProject,
      });
    }
    const changeSet: DesignChangeSet<TDocument> = {
      changeSetId: request.changeSetId,
      targetType: request.proposedValue.documentType,
      targetId,
      baseVersionId: request.baseVersionId,
      previousValue: latest.document,
      proposedValue: request.proposedValue,
      rationale: request.rationale,
      expectedResult: request.expectedResult,
      impactScope: request.impactScope,
      risk: request.risk,
      validationPlan: request.validationPlan,
      rollbackPlan: request.rollbackPlan,
      approvalRequirements: ["design:approve"],
      source: "assistant",
      status: "waiting-approval",
      createdBy: metadata.actorId,
      createdAt: metadata.occurredAt,
      approvedBy: null,
      approvedAt: null,
    };
    this.#repository.saveChangeSet(changeSet);
    return changeSet;
  }

  approveAndApplyChange<TDocument extends VersionedDesignDocument>(
    changeSetId: string,
    versionId: string,
    metadata: DesignCommandMetadata,
  ): AppliedDesignChange<TDocument> {
    const changeSet = this.#repository.getChangeSet(changeSetId) as DesignChangeSet<TDocument> | null;
    if (changeSet === null) {
      throw new DesignRoomError("CHANGESET_NOT_FOUND", "找不到待审批的 Design ChangeSet。", { changeSetId });
    }
    if (changeSet.status !== "waiting-approval") {
      throw new DesignRoomError("CHANGESET_NOT_APPROVABLE", "该 ChangeSet 当前不可审批。", {
        status: changeSet.status,
      });
    }
    const latest = this.#repository.latest<TDocument>(changeSet.targetType, changeSet.targetId);
    if (latest?.versionId !== changeSet.baseVersionId) {
      throw new DesignRoomError("BASE_VERSION_CONFLICT", "文档已变化，请重新生成 AI 建议。", {
        expected: latest?.versionId ?? null,
        actual: changeSet.baseVersionId,
      });
    }
    const applied: DesignChangeSet<TDocument> = {
      ...changeSet,
      status: "applied",
      approvedBy: metadata.actorId,
      approvedAt: metadata.occurredAt,
    };
    const version = this.#repository.saveVersion({
      versionId,
      document: changeSet.proposedValue,
      actorId: metadata.actorId,
      createdAt: metadata.occurredAt,
      rationale: changeSet.rationale,
      mode: metadata.mode,
      sourceChangeSetId: changeSet.changeSetId,
    });
    this.#repository.saveChangeSet(applied);
    return { changeSet: applied, version };
  }

  markFeatureReady(
    featureSpecId: string,
    intake: ProjectIntakeRecord,
    versionId: string,
    metadata: DesignCommandMetadata,
  ): DocumentVersion<FeatureSpec> {
    const latest = this.#repository.latest<FeatureSpec>("feature-spec", featureSpecId);
    if (latest === null) {
      throw new DesignRoomError("DOCUMENT_NOT_FOUND", "找不到待交给 Production Planner 的 Feature Spec。", {
        featureSpecId,
      });
    }
    const issues = validateFeatureForPlanning(latest.document, intake);
    if (issues.length > 0) {
      throw new DesignRoomError("DESIGN_NOT_ACTIONABLE", "Feature Spec 尚不可进入生产计划。", { issues });
    }
    return this.saveFeature(
      {
        versionId,
        document: { ...latest.document, status: "ready-for-planning" },
        rationale: "通过设计准备度检查，交给 Production Planner。",
      },
      metadata,
    );
  }

  createDecision(record: DecisionRecord): DecisionRecord {
    this.#repository.saveDecision(record);
    return record;
  }

  rejectAlternative(decisionId: string, alternativeId: string, rationale: string): DecisionRecord {
    const decision = this.requireDecision(decisionId);
    const updated = rejectDecisionAlternative(decision, alternativeId, rationale);
    this.#repository.saveDecision(updated);
    return updated;
  }

  acceptAlternative(
    decisionId: string,
    alternativeId: string,
    rationale: string,
    actorId: string,
    occurredAt: string,
  ): DecisionRecord {
    const decision = this.requireDecision(decisionId);
    const updated = acceptDecisionAlternative(decision, alternativeId, rationale, actorId, occurredAt);
    this.#repository.saveDecision(updated);
    return updated;
  }

  latestFeature(featureSpecId: string): DocumentVersion<FeatureSpec> | null {
    return this.#repository.latest("feature-spec", featureSpecId);
  }

  getChangeSet(changeSetId: string): DesignChangeSet | null {
    return this.#repository.getChangeSet(changeSetId);
  }

  private requireDecision(decisionId: string): DecisionRecord {
    const decision = this.#repository.getDecision(decisionId);
    if (decision === null) {
      throw new DesignRoomError("DECISION_NOT_FOUND", "找不到设计决策。", { decisionId });
    }
    return decision;
  }
}
