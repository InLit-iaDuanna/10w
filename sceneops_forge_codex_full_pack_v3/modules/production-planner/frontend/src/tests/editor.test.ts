import assert from "node:assert/strict";
import test from "node:test";

import {
  modeLabel,
  productionPlanDocument,
  restorePlannerState,
  serializePlannerState,
} from "../editors/editorState.ts";
import { keyDoorResponse } from "./support.ts";

test("editor renders graph, assignment, estimate basis, blocker count, and mode", async () => {
  const document = productionPlanDocument({ kind: "ready", data: await keyDoorResponse() });
  assert.equal(document.heading, "钥匙与家门分支");
  assert.equal(document.modeLabel, "MOCK · 确定性示例");
  assert.equal(document.sourceModeLabel, "Feature Spec：MOCK · 确定性示例");
  assert.match(document.message, /关键路径 60h/);
  assert.equal(document.taskRows.length, 12);
  assert.match(document.taskRows[0].assignment, /人工/);
  assert.match(document.taskRows[0].estimate, /预测/);
  assert.equal(document.criticalPathTaskIds.length, 9);
  assert.equal(document.milestoneRows.length, 6);
  assert.equal(document.blockerMessages.length, 0);
  assert.deepEqual(document.actions, ["production.plan.approval.open"]);
});

test("editor exposes loading, empty, failed, disconnected, permission, and disabled states", () => {
  const states = [
    { kind: "loading" } as const,
    { kind: "empty" } as const,
    { kind: "failed", code: "PLAN_FAILED", message: "计划失败", retryable: true } as const,
    { kind: "disconnected", retryable: true } as const,
    { kind: "permission_denied" } as const,
    { kind: "module_disabled" } as const,
  ];
  for (const state of states) {
    const document = productionPlanDocument(state);
    assert.equal(document.statusLabel, state.kind);
    assert.ok(document.message.length > 0);
    assert.equal(document.taskRows.length, 0);
  }
  assert.deepEqual(productionPlanDocument(states[1]).actions, ["production.plan.create"]);
  assert.deepEqual(productionPlanDocument(states[2]).actions, ["run.retry"]);
});

test("all truthfulness labels are explicit", () => {
  assert.match(modeLabel("live"), /LIVE/);
  assert.match(modeLabel("cached"), /CACHED/);
  assert.match(modeLabel("mock"), /MOCK/);
  assert.match(modeLabel("planned"), /PLANNED/);
  assert.match(modeLabel("blocked"), /BLOCKED/);
});

test("editor context pin and viewport state serialize deterministically", () => {
  const state = {
    selectedTaskId: "task:feature:key-and-door:logic",
    zoom: 1.25,
    panX: 20,
    panY: -8,
    contextBinding: {
      mode: "pinned" as const,
      projectId: "project:remember-home",
      featureId: "feature:key-and-door",
      planId: "plan:feature:key-and-door:r1",
    },
  };
  assert.deepEqual(restorePlannerState(serializePlannerState(state)), state);
});
