import assert from "node:assert/strict";
import {
  AssistantActionCoordinator,
  chatOnlyHomeFixture,
  moduleContribution,
} from "../index.ts";
import type {
  CommandRequest,
  WorkbenchContextSnapshot,
} from "../assistant-actions/coordinator.ts";

assert.equal(moduleContribution.editors[0]?.id, "assistant.conversation");
assert.deepEqual(
  chatOnlyHomeFixture.areas.map((area) => area.editorId),
  ["assistant.conversation"],
);

const context: WorkbenchContextSnapshot = {
  projectId: "prj_smoke",
  branchId: null,
  sceneId: null,
  selectedSceneObjectIds: [],
  selectedAssetIds: [],
  activeFeatureId: null,
  activeTaskId: null,
  activeChangeSetId: null,
  activeRenderJobId: null,
  activeBuildId: null,
  activePlaytestRunId: null,
  activeIssueId: null,
};
const executed: CommandRequest[] = [];
const coordinator = new AssistantActionCoordinator({
  inspect: async () => ({
    state: "available",
    layoutEffect: "material",
    missingPermissions: [],
    missingIntegrations: [],
    suggestedActions: [],
    approval: { required: false, state: "not_required" },
  }),
  preview: async () => ({
    mode: "planned",
    summary: "右侧拆分",
    changes: ["split:right"],
    targetDescription: "对话右侧",
  }),
  execute: async (request) => {
    executed.push(request);
    return { opened: true };
  },
});
const action = {
  actionId: "act_smoke_open_right",
  type: "workbench.open_editor",
  title: "在右侧打开 3D 视图",
  requiresConfirmation: true,
  input: {
    editorId: "scene.viewport.3d",
    placement: { mode: "split", direction: "right" },
  },
} as const;
const prepared = await coordinator.prepare(action, "assistant", context);
assert.equal(prepared.status, "awaiting_confirmation");
assert.equal(executed.length, 0);
const result = await coordinator.confirmLayoutAndExecute(action.actionId, context);
assert.equal(result.status, "executed");
assert.equal(executed[0]?.commandId, "workbench.open_editor");

console.log("conversation-home smoke: passed");
