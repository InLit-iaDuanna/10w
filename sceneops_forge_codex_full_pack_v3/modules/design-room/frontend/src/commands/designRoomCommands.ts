import type {
  ConversationFeatureDraftInput,
  DecisionRecord,
  DecisionRecordedPayload,
  DesignChangeSet,
  DesignCommandAvailability,
  DesignCommandContext,
  DesignCommandMetadata,
  DesignEventEnvelope,
  DesignOpenEditorAction,
  DocumentVersion,
  DocumentVersionedPayload,
  FeatureSpec,
  GddDocument,
  PlanningReadyPayload,
  ProjectBible,
  ProjectIntakeRecord,
  VersionedDesignDocument,
} from "../contracts.ts";
import { DesignRoomError } from "../contracts.ts";
import type {
  ProposeDesignChangeRequest,
  SaveDocumentRequest,
} from "../service.ts";
import { DesignRoomService } from "../service.ts";

export interface VersionedCommandResult<TDocument extends VersionedDesignDocument> {
  readonly version: DocumentVersion<TDocument>;
  readonly event: DesignEventEnvelope<DocumentVersionedPayload>;
}

export interface ConversationDraftResult extends VersionedCommandResult<FeatureSpec> {
  readonly openEditorAction: DesignOpenEditorAction;
}

export interface PlanningReadyResult {
  readonly version: DocumentVersion<FeatureSpec>;
  readonly events: readonly [
    DesignEventEnvelope<DocumentVersionedPayload>,
    DesignEventEnvelope<PlanningReadyPayload>,
  ];
}

export interface DecisionCommandResult {
  readonly decision: DecisionRecord;
  readonly event: DesignEventEnvelope<DecisionRecordedPayload>;
}

export function designCommandAvailability(
  context: DesignCommandContext,
  requiredPermissions: readonly string[],
): DesignCommandAvailability {
  if (!context.moduleEnabled) {
    return { available: false, code: "MODULE_DISABLED", message: "Design Room 模块已关闭。" };
  }
  const missing = requiredPermissions.find((permission) => !context.permissions.has(permission));
  if (missing !== undefined) {
    return { available: false, code: "PERMISSION_DENIED", message: `缺少权限：${missing}` };
  }
  return { available: true, code: "AVAILABLE", message: "可执行" };
}

function assertAvailable(context: DesignCommandContext, permissions: readonly string[]): void {
  const availability = designCommandAvailability(context, permissions);
  if (!availability.available) {
    const code = availability.code === "MODULE_DISABLED" ? "MODULE_DISABLED" : "PERMISSION_DENIED";
    throw new DesignRoomError(code, availability.message, {
      suggestedAction: code === "MODULE_DISABLED" ? "module.enable" : "permissions.request",
    });
  }
}

function assertActor(
  metadata: DesignCommandMetadata,
  expected: DesignCommandMetadata["actorType"],
): void {
  if (metadata.actorType !== expected) {
    throw new DesignRoomError(
      "INVALID_ACTOR",
      expected === "user"
        ? "该命令必须由用户直接执行；AI 修改请创建 Design ChangeSet。"
        : "该命令仅接收 assistant 产生的结构化草稿或建议。",
      { expected, actual: metadata.actorType },
    );
  }
}

function versionedEvent<TDocument extends VersionedDesignDocument>(
  version: DocumentVersion<TDocument>,
  metadata: DesignCommandMetadata,
  actorType: "user" | "assistant",
): DesignEventEnvelope<DocumentVersionedPayload> {
  return {
    eventId: metadata.eventId,
    eventType:
      version.documentType === "project-bible"
        ? "design.project_bible.versioned"
        : "design.feature_spec.versioned",
    eventVersion: 1,
    occurredAt: metadata.occurredAt,
    projectId: version.document.projectId,
    correlationId: metadata.correlationId,
    causationId: metadata.commandId,
    actor: { type: actorType, id: metadata.actorId },
    mode: version.mode,
    payload: {
      documentType: version.documentType,
      documentId: version.documentId,
      versionId: version.versionId,
      versionNumber: version.versionNumber,
    },
  };
}

function decisionEvent(
  decision: DecisionRecord,
  metadata: DesignCommandMetadata,
): DesignEventEnvelope<DecisionRecordedPayload> {
  const accepted = decision.alternatives.find((item) => item.disposition === "accepted");
  return {
    eventId: metadata.eventId,
    eventType: "design.decision.recorded",
    eventVersion: 1,
    occurredAt: metadata.occurredAt,
    projectId: decision.projectId,
    correlationId: metadata.correlationId,
    causationId: metadata.commandId,
    actor: { type: "user", id: metadata.actorId },
    mode: metadata.mode,
    payload: {
      decisionId: decision.decisionId,
      status: decision.status,
      acceptedAlternativeId: accepted?.alternativeId ?? null,
    },
  };
}

export function createDesignRoomCommandHandlers(service: DesignRoomService) {
  return {
    saveBible(
      context: DesignCommandContext,
      request: SaveDocumentRequest<ProjectBible>,
      metadata: DesignCommandMetadata,
    ): VersionedCommandResult<ProjectBible> {
      assertAvailable(context, ["design:write"]);
      assertActor(metadata, "user");
      const version = service.saveBible(request, metadata);
      return { version, event: versionedEvent(version, metadata, "user") };
    },

    saveGdd(
      context: DesignCommandContext,
      document: GddDocument,
      metadata: DesignCommandMetadata,
    ): GddDocument {
      assertAvailable(context, ["design:write"]);
      assertActor(metadata, "user");
      return service.saveGdd(document);
    },

    draftFeatureFromConversation(
      context: DesignCommandContext,
      input: ConversationFeatureDraftInput,
      versionId: string,
      metadata: DesignCommandMetadata,
    ): ConversationDraftResult {
      assertAvailable(context, ["design:write"]);
      assertActor(metadata, "assistant");
      const version = service.draftFeatureFromConversation(input, versionId, metadata);
      return {
        version,
        event: versionedEvent(version, metadata, "assistant"),
        openEditorAction: {
          type: "workbench.open_editor",
          editorId: "design.feature_spec",
          placement: { mode: "tab" },
          context: { projectId: input.projectId, activeFeatureId: input.featureSpecId },
          requireConfirmation: false,
        },
      };
    },

    saveFeature(
      context: DesignCommandContext,
      request: SaveDocumentRequest<FeatureSpec>,
      metadata: DesignCommandMetadata,
    ): VersionedCommandResult<FeatureSpec> {
      assertAvailable(context, ["design:write"]);
      assertActor(metadata, "user");
      if (request.document.status === "ready-for-planning") {
        throw new DesignRoomError(
          "DESIGN_NOT_ACTIONABLE",
          "请使用 design.feature_spec.mark_ready 执行项目入口与规格准备度检查。",
        );
      }
      const version = service.saveFeature(request, metadata);
      return { version, event: versionedEvent(version, metadata, "user") };
    },

    proposeChange<TDocument extends VersionedDesignDocument>(
      context: DesignCommandContext,
      request: ProposeDesignChangeRequest<TDocument>,
      metadata: DesignCommandMetadata,
    ): DesignChangeSet<TDocument> {
      assertAvailable(context, ["design:write"]);
      assertActor(metadata, "assistant");
      return service.proposeChange(request, metadata);
    },

    approveChange<TDocument extends VersionedDesignDocument>(
      context: DesignCommandContext,
      changeSetId: string,
      versionId: string,
      metadata: DesignCommandMetadata,
    ): VersionedCommandResult<TDocument> & { readonly changeSet: DesignChangeSet<TDocument> } {
      assertAvailable(context, ["design:approve"]);
      assertActor(metadata, "user");
      const result = service.approveAndApplyChange<TDocument>(changeSetId, versionId, metadata);
      return {
        ...result,
        event: versionedEvent(result.version, metadata, "user"),
      };
    },

    markFeatureReady(
      context: DesignCommandContext,
      featureSpecId: string,
      intake: ProjectIntakeRecord,
      versionId: string,
      readyEventId: string,
      metadata: DesignCommandMetadata,
    ): PlanningReadyResult {
      assertAvailable(context, ["design:write"]);
      assertActor(metadata, "user");
      const version = service.markFeatureReady(featureSpecId, intake, versionId, metadata);
      const versionEvent = versionedEvent(version, metadata, "user");
      const readyEvent: DesignEventEnvelope<PlanningReadyPayload> = {
        eventId: readyEventId,
        eventType: "design.feature_spec.marked_ready",
        eventVersion: 1,
        occurredAt: metadata.occurredAt,
        projectId: version.document.projectId,
        correlationId: metadata.correlationId,
        causationId: metadata.commandId,
        actor: { type: "user", id: metadata.actorId },
        mode: metadata.mode,
        payload: {
          featureSpecId: version.document.featureSpecId,
          featureVersionId: version.versionId,
          dependencyIds: version.document.dependencies.map((item) => item.dependencyId),
          acceptanceCriterionIds: version.document.acceptanceCriteria.map((item) => item.criterionId),
          requiredDeliverables: version.document.requiredDeliverables.map((item) => ({
            requirementId: item.requirementId,
            kind: item.kind,
          })),
          requiredTestIds: version.document.requiredTests.map((item) => item.testId),
        },
      };
      return { version, events: [versionEvent, readyEvent] };
    },

    createDecision(
      context: DesignCommandContext,
      decision: DecisionRecord,
      metadata: DesignCommandMetadata,
    ): DecisionCommandResult {
      assertAvailable(context, ["design:write"]);
      assertActor(metadata, "user");
      const saved = service.createDecision(decision);
      return { decision: saved, event: decisionEvent(saved, metadata) };
    },

    rejectAlternative(
      context: DesignCommandContext,
      decisionId: string,
      alternativeId: string,
      rationale: string,
      metadata: DesignCommandMetadata,
    ): DecisionCommandResult {
      assertAvailable(context, ["design:write"]);
      assertActor(metadata, "user");
      const decision = service.rejectAlternative(decisionId, alternativeId, rationale);
      return { decision, event: decisionEvent(decision, metadata) };
    },

    acceptAlternative(
      context: DesignCommandContext,
      decisionId: string,
      alternativeId: string,
      rationale: string,
      metadata: DesignCommandMetadata,
    ): DecisionCommandResult {
      assertAvailable(context, ["design:approve"]);
      assertActor(metadata, "user");
      const decision = service.acceptAlternative(
        decisionId,
        alternativeId,
        rationale,
        metadata.actorId,
        metadata.occurredAt,
      );
      return { decision, event: decisionEvent(decision, metadata) };
    },
  };
}

export type DesignRoomCommandHandlers = ReturnType<typeof createDesignRoomCommandHandlers>;
