import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { assistantActionTypes } from "../assistant-actions/types.ts";
import { validateAssistantAction } from "../assistant-actions/validate.ts";

function baseAction(type: string, input: Record<string, unknown>) {
  return {
    actionId: `act_${type.replaceAll(".", "_")}`,
    type,
    title: "测试操作",
    input,
  };
}

test("validates the right-side 3D view contract example", () => {
  const exampleUrl = new URL(
    "../../../contracts/examples/open-scene-view-right.action.json",
    import.meta.url,
  );
  const example = JSON.parse(readFileSync(exampleUrl, "utf8"));
  const result = validateAssistantAction(example);
  assert.equal(result.ok, true);
  if (result.ok) {
    assert.equal(result.value.type, "workbench.open_editor");
    assert.equal(result.value.requiresConfirmation, true);
  }
});

test("accepts every declared assistant action type with typed input", () => {
  const actions = [
    {
      ...baseAction("workbench.open_editor", {
        editorId: "scene.viewport.3d",
        placement: { mode: "split", direction: "right" },
      }),
      requiresConfirmation: true,
    },
    baseAction("project.create", {
      changeSetId: "changeset_project_create",
      name: "Remember Home",
      brief: "回家",
    }),
    baseAction("feature.create", {
      changeSetId: "changeset_feature_create",
      projectId: "prj_home",
      title: "钥匙和门",
      brief: "找到钥匙并开门",
    }),
    baseAction("workflow.run", {
      changeSetId: "changeset_workflow_run",
      projectId: "prj_home",
      workflowId: "workflow_feature_to_build",
      parameters: { featureId: "feature_key_door" },
    }),
    baseAction("artifact.open", { artifactId: "artifact_build_001" }),
    baseAction("issue.open_backpin", { issueId: "issue_door_visibility" }),
    baseAction("changeset.approval.request", { changeSetId: "changeset_fix_001" }),
  ];

  assert.deepEqual(actions.map((action) => action.type), assistantActionTypes);
  for (const action of actions) {
    assert.deepEqual(validateAssistantAction(action), { ok: true, value: action });
  }
});

test("rejects natural-language text and unknown command types", () => {
  const textResult = validateAssistantAction("打开右侧 3D 视图");
  assert.equal(textResult.ok, false);

  const unknownResult = validateAssistantAction(
    baseAction("shell.execute", { command: "rm -rf project" }),
  );
  assert.equal(unknownResult.ok, false);
  if (!unknownResult.ok) {
    assert.match(unknownResult.issues[0]?.message ?? "", /command ID/);
  }
});

test("rejects layout actions that could bypass confirmation", () => {
  const result = validateAssistantAction({
    ...baseAction("workbench.open_editor", {
      editorId: "scene.viewport.3d",
      placement: { mode: "split", direction: "right" },
    }),
    requiresConfirmation: false,
  });
  assert.equal(result.ok, false);
  if (!result.ok) {
    assert.equal(
      result.issues.some((issue) => issue.path === "$.requiresConfirmation"),
      true,
    );
  }
});

test("rejects malformed placement, duplicate context IDs, and unknown fields", () => {
  const result = validateAssistantAction({
    ...baseAction("workbench.open_editor", {
      editorId: "scene.viewport.3d",
      placement: { mode: "split", direction: "diagonal", force: true },
      context: { sceneObjectIds: ["obj_door", "obj_door"] },
    }),
    requiresConfirmation: true,
    bypassPermissions: true,
  });
  assert.equal(result.ok, false);
  if (!result.ok) {
    assert.equal(result.issues.some((issue) => issue.code === "unknown_field"), true);
    assert.equal(
      result.issues.some((issue) => issue.path.endsWith("direction")),
      true,
    );
    assert.equal(
      result.issues.some((issue) => issue.path.endsWith("sceneObjectIds")),
      true,
    );
  }
});

test("runtime validation matches stable-ID and JSON-only schema constraints", () => {
  const shortId = validateAssistantAction(
    baseAction("artifact.open", { artifactId: "x" }),
  );
  assert.equal(shortId.ok, false);

  const nonJsonParameters = validateAssistantAction(
    baseAction("workflow.run", {
      changeSetId: "changeset_workflow_run",
      projectId: "prj_home",
      workflowId: "workflow_build",
      parameters: new Date("2026-09-04T00:00:00Z"),
    }),
  );
  assert.equal(nonJsonParameters.ok, false);
});

test("rejects mutation actions that do not reference a ChangeSet", () => {
  for (const action of [
    baseAction("project.create", { name: "Unsafe Project" }),
    baseAction("feature.create", {
      projectId: "prj_home",
      title: "Unsafe Feature",
      brief: "missing ChangeSet",
    }),
    baseAction("workflow.run", {
      projectId: "prj_home",
      workflowId: "workflow_build",
      parameters: {},
    }),
  ]) {
    const result = validateAssistantAction(action);
    assert.equal(result.ok, false);
    if (!result.ok) {
      assert.equal(
        result.issues.some((issue) => issue.path === "$.input.changeSetId"),
        true,
      );
    }
  }
});
