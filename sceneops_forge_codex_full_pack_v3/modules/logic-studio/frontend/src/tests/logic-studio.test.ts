import assert from "node:assert/strict";
import test from "node:test";

import {
  createLogicEditorState,
  createOpenLogicEditorAction,
  logicCommandDefinitions,
  logicEditorDefinitions,
  moduleContribution,
  resolveLogicStudioContribution,
  restoreLogicEditorState,
  serializeLogicEditorState,
} from "../index.ts";

test("registers all six lazy logic editors", async () => {
  assert.equal(logicEditorDefinitions.length, 6);
  assert.equal(new Set(logicEditorDefinitions.map((editor) => editor.id)).size, 6);
  for (const editor of logicEditorDefinitions) {
    assert.equal(editor.category, "logic");
    assert.equal(editor.supportsContextBinding, true);
    assert.ok(editor.requiredPermissions.length > 0);
    const loaded = await editor.load();
    assert.equal(typeof loaded.default.createView, "function");
  }
});

test("renders loading empty success failure offline and permission states", async () => {
  const definition = logicEditorDefinitions[4];
  const runtime = (await definition.load()).default;
  const statuses = [
    "loading",
    "empty",
    "ready",
    "failed",
    "offline",
    "permission_denied",
  ] as const;
  const views = statuses.map((status) =>
    runtime.createView(
      definition,
      {
        ...createLogicEditorState(status, status === "ready" ? "mock" : "blocked"),
        ...(status === "failed" ? { errorCode: "LOAD_FAILED" } : {}),
      },
    ),
  );
  assert.deepEqual(views.map((view) => view.status), statuses);
  assert.equal(views[2].modeLabel, "MOCK");
  assert.deepEqual(views[3].actions, [{ id: "retry", label: "重试" }]);
  assert.equal(views[4].actions[0].id, "open_integration");
  assert.equal(views[5].actions[0].id, "request_permission");
});

test("serializes and restores pinned editor context", () => {
  const state = {
    ...createLogicEditorState("ready", "cached", {
      mode: "pinned" as const,
      context: {
        activeFeatureId: "feat_key_door_branch",
        selectedSceneObjectIds: ["sobj_home_door_01"],
      },
    }),
    selectedEntityIds: ["target_interaction"],
  };
  const restored = restoreLogicEditorState(serializeLogicEditorState(state));
  assert.deepEqual(restored, state);
  assert.throws(
    () => restoreLogicEditorState({ ...serializeLogicEditorState(state), schemaVersion: 2 }),
    /schemaVersion 1/,
  );
});

test("conversation command creates a confirmed workbench action", () => {
  const action = createOpenLogicEditorAction({
    target: "state_graph",
    context: { activeFeatureId: "feat_key_door_branch" },
  });
  assert.deepEqual(action, {
    type: "workbench.open_editor",
    editorId: "logic.state_graph",
    placement: { mode: "split", direction: "right" },
    context: { activeFeatureId: "feat_key_door_branch" },
    requireConfirmation: true,
  });
});

test("feature flag can disable the complete contribution", () => {
  assert.equal(resolveLogicStudioContribution(false), null);
  assert.equal(resolveLogicStudioContribution(true), moduleContribution);
});

test("dangerous code commands declare approval and Unity requirements", () => {
  const apply = logicCommandDefinitions.find(
    (command) => command.id === "logic.code_change.apply",
  );
  const rollback = logicCommandDefinitions.find(
    (command) => command.id === "logic.code_change.rollback",
  );
  assert.deepEqual(apply?.requiredIntegrations, ["unity"]);
  assert.equal(apply?.requiresApproval, true);
  assert.deepEqual(rollback?.requiredIntegrations, ["unity"]);
  assert.equal(rollback?.requiresApproval, true);
});
