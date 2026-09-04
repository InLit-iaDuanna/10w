import assert from "node:assert/strict";
import test from "node:test";

import {
  createProductionPlanCommand,
  invokeCreatePlanFromButton,
  invokeCreatePlanFromChat,
} from "../commands/createProductionPlan.ts";
import { openTaskInRecommendedEditor } from "../commands/openTask.ts";
import type { ProductionPlannerApi, WorkbenchCommandPort } from "../ports.ts";
import { keyDoorRequest, keyDoorResponse } from "./support.ts";

test("chat and button use the exact same create-plan handler", async () => {
  const response = await keyDoorResponse();
  const requests: unknown[] = [];
  const api: ProductionPlannerApi = {
    async createPlan(request) {
      requests.push(request);
      return response;
    },
  };
  const context = {
    api,
    permissions: new Set(["production-plan:write"]),
    moduleEnabled: true,
  };
  assert.equal(invokeCreatePlanFromChat, invokeCreatePlanFromButton);
  assert.equal(createProductionPlanCommand.execute, invokeCreatePlanFromChat);
  const chatResult = await invokeCreatePlanFromChat(context, keyDoorRequest());
  const buttonResult = await invokeCreatePlanFromButton(context, keyDoorRequest());
  assert.deepEqual(chatResult, buttonResult);
  assert.deepEqual(requests, [keyDoorRequest(), keyDoorRequest()]);
  assert.equal(chatResult.status, "succeeded");
  if (chatResult.status === "succeeded") {
    assert.equal(chatResult.openPlanAction.commandId, "workbench.open_editor");
    assert.equal(chatResult.openPlanAction.input.requireConfirmation, true);
  }
});

test("create-plan command exposes disabled, permission, and disconnected failures", async () => {
  const disconnectedApi: ProductionPlannerApi = {
    async createPlan() {
      throw new Error("offline");
    },
  };
  const request = keyDoorRequest();
  const disabled = await createProductionPlanCommand.execute(
    { api: disconnectedApi, permissions: new Set(), moduleEnabled: false },
    request,
  );
  const denied = await createProductionPlanCommand.execute(
    { api: disconnectedApi, permissions: new Set(), moduleEnabled: true },
    request,
  );
  const disconnected = await createProductionPlanCommand.execute(
    {
      api: disconnectedApi,
      permissions: new Set(["production-plan:write"]),
      moduleEnabled: true,
    },
    request,
  );
  assert.equal(disabled.status, "unavailable");
  assert.equal(disabled.code, "MODULE_DISABLED");
  assert.equal(denied.status, "unavailable");
  assert.equal(denied.code, "PERMISSION_DENIED");
  assert.equal(disconnected.status, "failed");
  if (disconnected.status === "failed") {
    assert.equal(disconnected.error.code, "PLANNER_DISCONNECTED");
    assert.equal(disconnected.error.retryable, true);
  }
});

test("opening a task dispatches the shell-owned typed editor command", async () => {
  const response = await keyDoorResponse();
  const calls: Array<{ commandId: string; input: unknown }> = [];
  const commands: WorkbenchCommandPort = {
    async dispatch(commandId, input) {
      calls.push({ commandId, input });
      return { accepted: true };
    },
  };
  const logicTask = response.plan.tasks.find((task) => task.workstream === "logic");
  assert.ok(logicTask);
  await openTaskInRecommendedEditor(commands, response.plan, logicTask);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].commandId, "workbench.open_editor");
  assert.deepEqual(calls[0].input, {
    editorId: "logic.gameplay-state",
    placement: { mode: "tab" },
    context: {
      projectId: "project:remember-home",
      activeFeatureId: "feature:key-and-door",
      activeTaskId: "task:feature:key-and-door:logic",
      productionPlanId: "plan:feature:key-and-door:r1",
    },
    requireConfirmation: true,
  });
});
