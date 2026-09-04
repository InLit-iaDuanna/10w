import test from "node:test";
import assert from "node:assert/strict";

import { createNewProjectIntake } from "../../../../project-intake/frontend/src/index.ts";
import {
  DesignRoomError,
  designCommandAvailability,
  validateFeatureSpec,
} from "../index.ts";
import type { FeatureSpec } from "../index.ts";
import { DesignRoomService } from "../service.ts";
import { InMemoryDesignDocumentRepository } from "../repository.ts";
import { createDesignRoomCommandHandlers } from "../commands/designRoomCommands.ts";
import buildFeatureSpecEditorView from "../editors/FeatureSpecEditor.ts";
import buildGddEditorView from "../editors/GddEditor.ts";
import {
  designFixtureMetadata,
  enabledDesignContext,
  findMyWayHomeIntakeForDesign,
  findMyWayHomeBible,
  findMyWayHomeGdd,
  keyDoorConversationDraft,
  keyDoorFeatureSpec,
  keyVisibilityDecision,
  warehouseEscapeFeatureSpec,
} from "../fixtures/designDocuments.ts";

function createHarness() {
  const repository = new InMemoryDesignDocumentRepository();
  const service = new DesignRoomService(repository);
  const handlers = createDesignRoomCommandHandlers(service);
  return { repository, service, handlers };
}

test("Project Bible versions retain structured content and produce a deterministic diff", () => {
  const { handlers, service } = createHarness();
  const first = handlers.saveBible(
    enabledDesignContext,
    { versionId: "ver_bible_001", document: findMyWayHomeBible, rationale: "初始批准版本" },
    designFixtureMetadata,
  );
  const revised = { ...findMyWayHomeBible, gameGoal: "找到钥匙、打开家门并安全完成归家目标。" };
  const second = handlers.saveBible(
    enabledDesignContext,
    { versionId: "ver_bible_002", document: revised, rationale: "明确钥匙目标" },
    { ...designFixtureMetadata, eventId: "evt_bible_002" },
  );

  assert.equal(first.version.versionNumber, 1);
  assert.equal(second.version.versionNumber, 2);
  assert.equal(first.event.eventType, "design.project_bible.versioned");
  assert.deepEqual(
    service.diff("project-bible", findMyWayHomeBible.bibleId, "ver_bible_001", "ver_bible_002"),
    [{
      path: "/gameGoal",
      kind: "changed",
      before: findMyWayHomeBible.gameGoal,
      after: revised.gameGoal,
    }],
  );
});

test("Feature Spec versions expose exact changed paths", () => {
  const { handlers, service } = createHarness();
  handlers.saveFeature(
    enabledDesignContext,
    { versionId: "ver_feature_001", document: keyDoorFeatureSpec, rationale: "初始规格" },
    designFixtureMetadata,
  );
  const revised = { ...keyDoorFeatureSpec, playerValue: "通过发现钥匙获得更强的归家成就感。" };
  handlers.saveFeature(
    enabledDesignContext,
    { versionId: "ver_feature_002", document: revised, rationale: "澄清玩家价值" },
    { ...designFixtureMetadata, eventId: "evt_feature_002" },
  );
  const diff = service.diff("feature-spec", keyDoorFeatureSpec.featureSpecId, "ver_feature_001", "ver_feature_002");
  assert.deepEqual(diff.map((entry) => entry.path), ["/playerValue"]);
  assert.equal(diff[0]?.kind, "changed");
});

test("conversation command creates an unconfirmed draft and opens Feature Spec editor", () => {
  const { handlers } = createHarness();
  const result = handlers.draftFeatureFromConversation(
    enabledDesignContext,
    keyDoorConversationDraft,
    "ver_conversation_001",
    { ...designFixtureMetadata, actorId: "assistant_sceneops", actorType: "assistant" },
  );

  assert.equal(result.version.document.status, "draft");
  assert.equal(result.version.document.assumptions[0]?.status, "unconfirmed");
  assert.equal(result.event.actor.type, "assistant");
  assert.equal(result.openEditorAction.editorId, "design.feature_spec");
  assert.equal(result.openEditorAction.context.activeFeatureId, "feature_key_door_branch");
  assert.ok(validateFeatureSpec(result.version.document).some((issue) => issue.code === "UNCONFIRMED_ASSUMPTION"));
});

test("actionable Feature Spec emits a typed planning-ready event without creating tasks", () => {
  const { handlers } = createHarness();
  assert.throws(
    () => handlers.saveFeature(
      enabledDesignContext,
      { versionId: "ver_bypass_ready", document: { ...keyDoorFeatureSpec, status: "ready-for-planning" }, rationale: "bypass" },
      designFixtureMetadata,
    ),
    (error: unknown) => error instanceof DesignRoomError && error.code === "DESIGN_NOT_ACTIONABLE",
  );
  handlers.saveFeature(
    enabledDesignContext,
    { versionId: "ver_feature_ready_base", document: keyDoorFeatureSpec, rationale: "准备度基线" },
    designFixtureMetadata,
  );
  const intake = createNewProjectIntake(findMyWayHomeIntakeForDesign);
  const result = handlers.markFeatureReady(
    enabledDesignContext,
    keyDoorFeatureSpec.featureSpecId,
    intake,
    "ver_feature_ready_001",
    "evt_feature_marked_ready_001",
    { ...designFixtureMetadata, eventId: "evt_feature_versioned_ready_001" },
  );

  assert.equal(result.version.document.status, "ready-for-planning");
  assert.deepEqual(result.events.map((event) => event.eventType), [
    "design.feature_spec.versioned",
    "design.feature_spec.marked_ready",
  ]);
  assert.deepEqual(result.events[1].payload.acceptanceCriterionIds, ["ac_key_required", "ac_door_opens"]);
  assert.equal("tasks" in result.events[1].payload, false);
});

test("planning handoff is blocked for incomplete intake or unresolved AI assumptions", () => {
  const { handlers } = createHarness();
  const draft = handlers.draftFeatureFromConversation(
    enabledDesignContext,
    keyDoorConversationDraft,
    "ver_unconfirmed_draft",
    { ...designFixtureMetadata, actorId: "assistant_sceneops", actorType: "assistant" },
  );
  const incompleteIntake = createNewProjectIntake({
    intakeId: "intake_incomplete",
    projectId: draft.version.document.projectId,
    projectName: "Incomplete",
    actorId: "usr_designer",
    occurredAt: "2026-09-04T05:00:00Z",
    mode: "mock",
  });
  assert.throws(
    () => handlers.markFeatureReady(
      enabledDesignContext,
      draft.version.document.featureSpecId,
      incompleteIntake,
      "ver_should_not_exist",
      "evt_should_not_exist",
      designFixtureMetadata,
    ),
    (error: unknown) => {
      if (!(error instanceof DesignRoomError) || error.code !== "DESIGN_NOT_ACTIONABLE") return false;
      const issues = error.details.issues as readonly { code: string }[];
      return issues.some((issue) => issue.code === "PROJECT_INTAKE_NOT_READY") &&
        issues.some((issue) => issue.code === "UNCONFIRMED_ASSUMPTION");
    },
  );
});

test("decision alternatives require explicit reject rationale before one acceptance", () => {
  const { handlers } = createHarness();
  handlers.createDecision(enabledDesignContext, keyVisibilityDecision, designFixtureMetadata);
  assert.throws(
    () => handlers.rejectAlternative(
      enabledDesignContext,
      keyVisibilityDecision.decisionId,
      "alt_emissive",
      "",
      designFixtureMetadata,
    ),
    (error: unknown) => error instanceof DesignRoomError && error.code === "INVALID_DECISION_RATIONALE",
  );
  assert.throws(
    () => handlers.acceptAlternative(
      enabledDesignContext,
      keyVisibilityDecision.decisionId,
      "alt_warm_light",
      "符合项目视觉规则。",
      designFixtureMetadata,
    ),
    (error: unknown) => error instanceof DesignRoomError && error.code === "PENDING_ALTERNATIVES",
  );
  const rejected = handlers.rejectAlternative(
    enabledDesignContext,
    keyVisibilityDecision.decisionId,
    "alt_emissive",
    "自发光会削弱写实氛围。",
    { ...designFixtureMetadata, eventId: "evt_decision_reject" },
  );
  const accepted = handlers.acceptAlternative(
    enabledDesignContext,
    keyVisibilityDecision.decisionId,
    "alt_warm_light",
    "暖光同时满足可见性与 Project Bible。",
    { ...designFixtureMetadata, eventId: "evt_decision_accept" },
  );
  assert.equal(rejected.decision.alternatives[0]?.disposition, "rejected");
  assert.equal(accepted.decision.status, "decided");
  assert.equal(accepted.event.payload.acceptedAlternativeId, "alt_warm_light");
  assert.ok(accepted.decision.alternatives.every((alternative) => alternative.rationale !== null));
});

test("AI change does not mutate a document until an authorized approval applies it", () => {
  const { handlers, service } = createHarness();
  handlers.saveFeature(
    enabledDesignContext,
    { versionId: "ver_change_base", document: keyDoorFeatureSpec, rationale: "ChangeSet base" },
    designFixtureMetadata,
  );
  assert.throws(
    () => handlers.saveFeature(
      enabledDesignContext,
      { versionId: "ver_direct_ai_write", document: { ...keyDoorFeatureSpec, goal: "绕过审批" }, rationale: "direct" },
      { ...designFixtureMetadata, actorId: "assistant_sceneops", actorType: "assistant" },
    ),
    (error: unknown) => error instanceof DesignRoomError && error.code === "INVALID_ACTOR",
  );
  const proposed = { ...keyDoorFeatureSpec, goal: "玩家找到明确可见的钥匙后才能打开家门并完成目标。" };
  const changeSet = handlers.proposeChange(
    enabledDesignContext,
    {
      changeSetId: "changeset_feature_goal_001",
      baseVersionId: "ver_change_base",
      proposedValue: proposed,
      rationale: "补充可见性要求",
      expectedResult: "钥匙目标更可测试",
      impactScope: ["feature_key_door_branch"],
      risk: "low",
      validationPlan: ["复核验收标准", "运行钥匙可见性测试"],
      rollbackPlan: ["恢复 ver_change_base"],
    },
    { ...designFixtureMetadata, actorId: "assistant_sceneops", actorType: "assistant" },
  );
  assert.equal(changeSet.status, "waiting-approval");
  assert.equal(service.latestFeature(keyDoorFeatureSpec.featureSpecId)?.document.goal, keyDoorFeatureSpec.goal);

  const noApproval = { moduleEnabled: true, permissions: new Set(["design:read", "design:write"]) };
  assert.throws(
    () => handlers.approveChange(noApproval, changeSet.changeSetId, "ver_change_applied", designFixtureMetadata),
    (error: unknown) => error instanceof DesignRoomError && error.code === "PERMISSION_DENIED",
  );
  const applied = handlers.approveChange<FeatureSpec>(
    enabledDesignContext,
    changeSet.changeSetId,
    "ver_change_applied",
    { ...designFixtureMetadata, eventId: "evt_change_applied" },
  );
  assert.equal(applied.changeSet.status, "applied");
  assert.equal(applied.version.document.goal, proposed.goal);
  assert.equal(applied.version.sourceChangeSetId, changeSet.changeSetId);
});

test("stale AI ChangeSet is rejected instead of silently rebased", () => {
  const { handlers } = createHarness();
  handlers.saveFeature(enabledDesignContext, {
    versionId: "ver_conflict_base",
    document: keyDoorFeatureSpec,
    rationale: "base",
  }, designFixtureMetadata);
  const changeSet = handlers.proposeChange(enabledDesignContext, {
    changeSetId: "changeset_conflict",
    baseVersionId: "ver_conflict_base",
    proposedValue: { ...keyDoorFeatureSpec, playerValue: "AI proposal" },
    rationale: "proposal",
    expectedResult: "clearer value",
    impactScope: ["feature_key_door_branch"],
    risk: "low",
    validationPlan: ["review"],
    rollbackPlan: ["restore base"],
  }, { ...designFixtureMetadata, actorId: "assistant_sceneops", actorType: "assistant" });
  handlers.saveFeature(enabledDesignContext, {
    versionId: "ver_conflicting_user_edit",
    document: { ...keyDoorFeatureSpec, playerValue: "User edit" },
    rationale: "user edit",
  }, { ...designFixtureMetadata, eventId: "evt_user_edit" });

  assert.throws(
    () => handlers.approveChange(enabledDesignContext, changeSet.changeSetId, "ver_never_written", designFixtureMetadata),
    (error: unknown) => error instanceof DesignRoomError && error.code === "BASE_VERSION_CONFLICT",
  );
});

test("structured GDD and second-game fixture remain reusable project data", () => {
  const { handlers } = createHarness();
  const saved = handlers.saveGdd(enabledDesignContext, findMyWayHomeGdd, designFixtureMetadata);
  assert.equal(saved.gameplaySystems[0]?.inputs[0]?.id, "input_interact");
  assert.equal(saved.gameplaySystems[0]?.outputs[0]?.id, "output_door_state");
  assert.deepEqual(validateFeatureSpec(warehouseEscapeFeatureSpec), []);

  const readyAccess = { moduleEnabled: true, hasReadPermission: true, loading: false, connected: true, errorMessage: null };
  assert.equal(buildGddEditorView(readyAccess, saved, "mock").state, "ready");
  assert.equal(buildFeatureSpecEditorView(readyAccess, warehouseEscapeFeatureSpec, "mock").state, "ready");
});

test("module-disabled, permission, and disconnected editor states are explicit", () => {
  assert.equal(designCommandAvailability({ moduleEnabled: false, permissions: new Set() }, ["design:write"]).code, "MODULE_DISABLED");
  assert.equal(designCommandAvailability({ moduleEnabled: true, permissions: new Set() }, ["design:write"]).code, "PERMISSION_DENIED");
  const disconnected = buildFeatureSpecEditorView({
    moduleEnabled: true,
    hasReadPermission: true,
    loading: false,
    connected: false,
    errorMessage: null,
  }, null, "blocked");
  const disabled = buildFeatureSpecEditorView({
    moduleEnabled: false,
    hasReadPermission: true,
    loading: false,
    connected: true,
    errorMessage: null,
  }, null, "blocked");
  assert.equal(disconnected.state, "disconnected");
  assert.equal(disabled.state, "module-disabled");
});
