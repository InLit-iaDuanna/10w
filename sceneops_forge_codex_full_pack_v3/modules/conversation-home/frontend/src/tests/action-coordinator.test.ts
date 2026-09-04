import assert from "node:assert/strict";
import test from "node:test";
import {
  AssistantActionCoordinator,
  type CommandAvailability,
  type CommandRequest,
  type LayoutActionPreview,
  type WorkbenchCommandBusPort,
  type WorkbenchContextSnapshot,
} from "../assistant-actions/coordinator.ts";
import type { JsonValue } from "../contracts/json.ts";

const context: WorkbenchContextSnapshot = {
  projectId: "prj_home",
  branchId: "branch_main",
  sceneId: "scn_hallway",
  selectedSceneObjectIds: ["obj_door_01"],
  selectedAssetIds: [],
  activeFeatureId: "feature_key_door",
  activeTaskId: null,
  activeChangeSetId: null,
  activeRenderJobId: null,
  activeBuildId: null,
  activePlaytestRunId: null,
  activeIssueId: null,
};

function available(): CommandAvailability {
  return {
    state: "available",
    layoutEffect: "none",
    missingPermissions: [],
    missingIntegrations: [],
    suggestedActions: [],
    approval: { required: false, state: "not_required" },
  };
}

class FakeCommandBus implements WorkbenchCommandBusPort {
  availability = available();
  readonly inspected: CommandRequest[] = [];
  readonly previewed: CommandRequest[] = [];
  readonly executed: CommandRequest[] = [];

  async inspect(request: CommandRequest): Promise<CommandAvailability> {
    this.inspected.push(request);
    return this.availability;
  }

  async preview(request: CommandRequest): Promise<LayoutActionPreview> {
    this.previewed.push(request);
    return {
      mode: "planned",
      summary: "在右侧创建拆分区域",
      changes: ["split:right", "open:scene.viewport.3d"],
      targetDescription: "对话右侧",
    };
  }

  async execute<TResult extends JsonValue = JsonValue>(
    request: CommandRequest,
  ): Promise<TResult> {
    this.executed.push(request);
    return { ok: true } as unknown as TResult;
  }
}

function openEditorAction() {
  return {
    actionId: "act_open_scene_right_001",
    type: "workbench.open_editor",
    title: "在右侧打开 3D 视图",
    requiresConfirmation: true,
    input: {
      editorId: "scene.viewport.3d",
      placement: { mode: "split", direction: "right" },
    },
  } as const;
}

test("layout action previews without execution and requires the explicit confirmation path", async () => {
  const bus = new FakeCommandBus();
  const coordinator = new AssistantActionCoordinator(bus);
  const prepared = await coordinator.prepare(openEditorAction(), "assistant", context);

  assert.equal(prepared.status, "awaiting_confirmation");
  assert.equal(bus.previewed.length, 1);
  assert.equal(bus.executed.length, 0);

  const bypassAttempt = await coordinator.executePrepared(
    "act_open_scene_right_001",
    context,
  );
  assert.equal(bypassAttempt.status, "rejected");
  assert.equal(bus.executed.length, 0);

  const confirmed = await coordinator.confirmLayoutAndExecute(
    "act_open_scene_right_001",
    context,
  );
  assert.equal(confirmed.status, "executed");
  assert.equal(bus.executed.length, 1);
  assert.equal(bus.inspected.length, 2, "availability is checked again at execution");
});

test("chat and button surfaces reach the same command ID and input", async () => {
  const bus = new FakeCommandBus();
  const coordinator = new AssistantActionCoordinator(bus);
  const assistantAction = {
    actionId: "act_project_assistant",
    type: "project.create",
    title: "创建项目",
    input: {
      changeSetId: "changeset_project_create",
      name: "Remember Home",
      brief: "回家",
    },
  } as const;
  const buttonAction = {
    ...assistantAction,
    actionId: "act_project_button",
  };

  const fromAssistant = await coordinator.prepare(assistantAction, "assistant", context);
  const fromButton = await coordinator.prepare(buttonAction, "button", context);
  assert.equal(fromAssistant.status, "ready");
  assert.equal(fromButton.status, "ready");
  await coordinator.executePrepared(assistantAction.actionId, context);
  await coordinator.executePrepared(buttonAction.actionId, context);

  assert.equal(bus.executed.length, 2);
  assert.equal(bus.executed[0]?.commandId, bus.executed[1]?.commandId);
  assert.deepEqual(bus.executed[0]?.input, bus.executed[1]?.input);
  assert.deepEqual(
    bus.executed.map((request) => request.source.surface),
    ["assistant", "button"],
  );
});

test("permission and integration failures stay visible and never execute", async () => {
  const bus = new FakeCommandBus();
  bus.availability = {
    state: "unavailable",
    layoutEffect: "material",
    code: "INTEGRATION_OFFLINE",
    message: "Unity 未连接。",
    missingPermissions: ["scene:read"],
    missingIntegrations: ["unity"],
    suggestedActions: [
      {
        commandId: "integration.open",
        title: "打开集成中心",
        input: { integrationId: "unity" },
      },
    ],
    approval: { required: false, state: "not_required" },
  };
  const coordinator = new AssistantActionCoordinator(bus);
  const prepared = await coordinator.prepare(openEditorAction(), "assistant", context);

  assert.equal(prepared.status, "unavailable");
  if (prepared.status === "unavailable") {
    assert.equal(prepared.error.mode, "blocked");
    assert.deepEqual(prepared.error.missingPermissions, ["scene:read"]);
    assert.deepEqual(prepared.error.missingIntegrations, ["unity"]);
    assert.equal(prepared.error.suggestedActions[0]?.commandId, "integration.open");
  }
  assert.equal(bus.previewed.length, 0);
  assert.equal(bus.executed.length, 0);
});

test("approval policy cannot be bypassed by an assistant action", async () => {
  const bus = new FakeCommandBus();
  bus.availability = {
    ...available(),
    approval: {
      required: true,
      state: "waiting",
      approvalId: "approval_changeset_001",
    },
  };
  const coordinator = new AssistantActionCoordinator(bus);
  const action = {
    actionId: "act_workflow_run_001",
    type: "workflow.run",
    title: "运行工作流",
    input: {
      changeSetId: "changeset_workflow_run_001",
      projectId: "prj_home",
      workflowId: "workflow_build",
      parameters: {},
    },
  } as const;

  const prepared = await coordinator.prepare(action, "assistant", context);
  assert.equal(prepared.status, "waiting_approval");
  const waiting = await coordinator.executePrepared(action.actionId, context);
  assert.deepEqual(waiting, {
    status: "waiting_approval",
    approvalId: "approval_changeset_001",
  });
  assert.equal(bus.executed.length, 0);

  bus.availability = {
    ...available(),
    approval: {
      required: true,
      state: "approved",
      approvalId: "approval_changeset_001",
    },
  };
  const executed = await coordinator.executePrepared(action.actionId, context);
  assert.equal(executed.status, "executed");
  assert.equal(bus.executed.length, 1);
});

test("a rejected approval is reported as a terminal unavailable state", async () => {
  const bus = new FakeCommandBus();
  bus.availability = {
    ...available(),
    message: "发布审批已拒绝。",
    approval: {
      required: true,
      state: "rejected",
      approvalId: "approval_rejected_001",
    },
  };
  const coordinator = new AssistantActionCoordinator(bus);
  const prepared = await coordinator.prepare(
    {
      actionId: "act_rejected_workflow",
      type: "workflow.run",
      title: "运行发布工作流",
      input: {
        changeSetId: "changeset_workflow_release",
        projectId: "prj_home",
        workflowId: "workflow_release",
        parameters: {},
      },
    },
    "assistant",
    context,
  );
  assert.equal(prepared.status, "unavailable");
  if (prepared.status === "unavailable") {
    assert.equal(prepared.error.code, "APPROVAL_REJECTED");
  }
  assert.equal(bus.executed.length, 0);
});

test("an action becoming unavailable between preview and confirmation is rejected", async () => {
  const bus = new FakeCommandBus();
  const coordinator = new AssistantActionCoordinator(bus);
  await coordinator.prepare(openEditorAction(), "assistant", context);
  bus.availability = {
    state: "unavailable",
    layoutEffect: "material",
    code: "PERMISSION_DENIED",
    message: "权限已变更。",
    missingPermissions: ["scene:read"],
    missingIntegrations: [],
    suggestedActions: [],
    approval: { required: false, state: "not_required" },
  };

  const result = await coordinator.confirmLayoutAndExecute(
    "act_open_scene_right_001",
    context,
  );
  assert.equal(result.status, "rejected");
  assert.equal(bus.executed.length, 0);
});

test("prepared actions cannot be changed through caller mutation or duplicate IDs", async () => {
  const bus = new FakeCommandBus();
  const coordinator = new AssistantActionCoordinator(bus);
  const action = {
    actionId: "act_project_immutable",
    type: "project.create",
    title: "创建项目",
    input: {
      changeSetId: "changeset_project_immutable",
      name: "Original Project",
    },
  };
  const prepared = await coordinator.prepare(action, "assistant", context);
  assert.equal(prepared.status, "ready");

  action.input.name = "Mutated Project";
  const duplicate = await coordinator.prepare(
    {
      ...action,
      input: {
        changeSetId: "changeset_project_replacement",
        name: "Replacement Project",
      },
    },
    "assistant",
    context,
  );
  assert.equal(duplicate.status, "invalid");

  await coordinator.executePrepared(action.actionId, context);
  assert.deepEqual(bus.executed[0]?.input, {
    changeSetId: "changeset_project_immutable",
    name: "Original Project",
  });
});

test("domain actions that report a material layout effect also require preview and confirmation", async () => {
  const bus = new FakeCommandBus();
  bus.availability = { ...available(), layoutEffect: "material" };
  const coordinator = new AssistantActionCoordinator(bus);
  const action = {
    actionId: "act_artifact_layout_001",
    type: "artifact.open",
    title: "打开产物",
    input: { artifactId: "artifact_build_001" },
  } as const;

  const prepared = await coordinator.prepare(action, "assistant", context);
  assert.equal(prepared.status, "awaiting_confirmation");
  assert.equal(bus.previewed.length, 1);
  assert.equal(bus.executed.length, 0);
  const direct = await coordinator.executePrepared(action.actionId, context);
  assert.equal(direct.status, "rejected");
  const confirmed = await coordinator.confirmLayoutAndExecute(
    action.actionId,
    context,
  );
  assert.equal(confirmed.status, "executed");
});
