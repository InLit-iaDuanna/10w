import test from "node:test";
import assert from "node:assert/strict";

import {
  DeterministicProjectScanAdapter,
  ProjectIntakeError,
  commandAvailability,
  validateIntakeForActivation,
} from "../index.ts";
import { InMemoryProjectIntakeRepository } from "../repository.ts";
import { ProjectIntakeService } from "../service.ts";
import { createProjectIntakeCommandHandlers } from "../commands/projectIntakeCommands.ts";
import buildProjectIntakeEditorView from "../editors/ProjectIntakeEditor.ts";
import {
  enabledProjectContext,
  findMyWayHomeNewProject,
  fixtureCommandMetadata,
  warehouseEscapeRoot,
  warehouseEscapeScanHealth,
  warehouseEscapeScanInput,
  warehouseEscapeScanReport,
} from "../fixtures/projects.ts";

function createHarness(health = warehouseEscapeScanHealth) {
  const repository = new InMemoryProjectIntakeRepository();
  const service = new ProjectIntakeService(repository);
  const adapter = new DeterministicProjectScanAdapter(health, warehouseEscapeScanReport);
  const handlers = createProjectIntakeCommandHandlers(
    service,
    new Map([[adapter.adapterId, adapter]]),
  );
  return { repository, service, handlers, adapter };
}

test("new-project chat command creates a ready draft and opens the structured editor", () => {
  const { handlers } = createHarness();
  const result = handlers.createNew(
    enabledProjectContext,
    findMyWayHomeNewProject,
    fixtureCommandMetadata,
  );

  assert.equal(result.record.status, "ready");
  assert.equal(result.record.fields.targetPlatforms.confidence, "confirmed");
  assert.equal(result.event.eventType, "project.intake.drafted");
  assert.equal(result.event.mode, "mock");
  assert.deepEqual(result.openEditorAction, {
    type: "workbench.open_editor",
    editorId: "project.intake",
    placement: { mode: "tab" },
    context: { projectId: "prj_find_my_way_home" },
    requireConfirmation: false,
  });
});

test("missing target platform and project root are explicit validation failures", () => {
  const { handlers } = createHarness();
  const result = handlers.createNew(
    enabledProjectContext,
    {
      intakeId: "intake_missing_critical",
      projectId: "prj_missing_critical",
      projectName: "Missing Settings",
      actorId: "usr_designer",
      occurredAt: "2026-09-04T03:00:00Z",
      mode: "mock",
    },
    fixtureCommandMetadata,
  );
  assert.equal(result.record.status, "draft");
  assert.deepEqual(
    validateIntakeForActivation(result.record).map((issue) => issue.code),
    ["MISSING_TARGET_PLATFORM", "MISSING_PROJECT_ROOT"],
  );
});

test("conversation values remain inferred until individual user confirmations", () => {
  const { handlers } = createHarness();
  const result = handlers.createFromConversation(
    enabledProjectContext,
    {
      ...findMyWayHomeNewProject,
      intakeId: "intake_conversation",
      sourceMessageId: "msg_project_brief_001",
    },
    { ...fixtureCommandMetadata, actorId: "assistant_sceneops" },
  );

  assert.equal(result.record.status, "needs-confirmation");
  assert.equal(result.record.fields.targetPlatforms.confidence, "inferred");
  assert.equal(result.record.fields.projectRoots.confidence, "inferred");
  assert.ok(result.event.payload.inferredFields.includes("engine"));

  const platformConfirmed = handlers.confirmField(
    enabledProjectContext,
    {
      intakeId: result.record.intakeId,
      field: "targetPlatforms",
      value: ["Windows", "macOS"],
    },
    { ...fixtureCommandMetadata, eventId: "evt_confirm_platform" },
  );
  const rootConfirmed = handlers.confirmField(
    enabledProjectContext,
    {
      intakeId: result.record.intakeId,
      field: "projectRoots",
      value: findMyWayHomeNewProject.projectRoots!,
    },
    { ...fixtureCommandMetadata, eventId: "evt_confirm_root" },
  );
  assert.equal(platformConfirmed.record.status, "needs-confirmation");
  assert.equal(rootConfirmed.record.status, "ready");
  assert.equal(rootConfirmed.event.eventType, "project.intake.field_confirmed");
});

test("existing-project partial scan normalizes adapter data without confirming it", async () => {
  const { handlers, adapter } = createHarness();
  const result = await handlers.scanExisting(
    enabledProjectContext,
    warehouseEscapeScanInput,
    { ...fixtureCommandMetadata, eventId: "evt_scan_warehouse" },
  );

  assert.equal(result.record.kind, "existing-project");
  assert.equal(result.record.mode, "mock");
  assert.equal(result.record.fields.projectRoots.confidence, "confirmed");
  assert.equal(result.record.fields.targetPlatforms.confidence, "inferred");
  assert.equal(result.record.fields.teamRoles.confidence, "missing");
  assert.equal(result.record.status, "needs-confirmation");
  assert.equal(result.record.scanReference?.adapterVersion, "0.1.0-fixture");
  assert.deepEqual(result.record.scanReference?.warnings, ["未发现团队角色与性能预算。"]);
  assert.deepEqual((await adapter.capabilities()).detectableFields, [
    "dccs",
    "engine",
    "integrationRequirements",
    "projectName",
    "targetPlatforms",
  ]);
});

test("scan rejects missing or relative project roots before calling the adapter", async () => {
  const { handlers } = createHarness();
  await assert.rejects(
    handlers.scanExisting(
      enabledProjectContext,
      { ...warehouseEscapeScanInput, projectRoot: null },
      fixtureCommandMetadata,
    ),
    (error: unknown) => error instanceof ProjectIntakeError && error.code === "MISSING_PROJECT_ROOT",
  );
  await assert.rejects(
    handlers.scanExisting(
      enabledProjectContext,
      { ...warehouseEscapeScanInput, projectRoot: { ...warehouseEscapeRoot, absolutePath: "relative/project" } },
      fixtureCommandMetadata,
    ),
    (error: unknown) => error instanceof ProjectIntakeError && error.code === "INVALID_PROJECT_ROOT",
  );
});

test("existing-project scan supports cancellation with a structured failure", async () => {
  const { handlers } = createHarness();
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(
    handlers.scanExisting(
      enabledProjectContext,
      warehouseEscapeScanInput,
      fixtureCommandMetadata,
      controller.signal,
    ),
    (error: unknown) => error instanceof ProjectIntakeError && error.code === "SCAN_CANCELLED",
  );
});

test("module disabled, permission denied, and integration offline states are visible", async () => {
  assert.equal(
    commandAvailability({ moduleEnabled: false, permissions: new Set() }, ["project:write"]).code,
    "MODULE_DISABLED",
  );
  assert.equal(
    commandAvailability({ moduleEnabled: true, permissions: new Set() }, ["project:write"]).code,
    "PERMISSION_DENIED",
  );

  const offline = { status: "offline" as const, checkedAt: "2026-09-04T03:00:00Z", message: "Unity 未连接。" };
  const { handlers } = createHarness(offline);
  await assert.rejects(
    handlers.scanExisting(enabledProjectContext, warehouseEscapeScanInput, fixtureCommandMetadata),
    (error: unknown) => error instanceof ProjectIntakeError && error.code === "INTEGRATION_OFFLINE",
  );

  assert.equal(buildProjectIntakeEditorView({
    moduleEnabled: false,
    hasReadPermission: true,
    loading: false,
    integrationHealth: null,
    record: null,
    errorMessage: null,
  }).state, "module-disabled");
  assert.equal(buildProjectIntakeEditorView({
    moduleEnabled: true,
    hasReadPermission: false,
    loading: false,
    integrationHealth: null,
    record: null,
    errorMessage: null,
  }).state, "permission-denied");
  assert.equal(buildProjectIntakeEditorView({
    moduleEnabled: true,
    hasReadPermission: true,
    loading: false,
    integrationHealth: offline,
    record: null,
    errorMessage: null,
  }).state, "integration-offline");
});
