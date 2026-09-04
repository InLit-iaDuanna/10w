import assert from "node:assert/strict";
import test from "node:test";

import { buildPipelineEditorState, moduleContribution, type PipelineSnapshot } from "../index.ts";

const base: PipelineSnapshot = {
  loading: false,
  permissionGranted: true,
  integrationConnected: true,
  run: null,
};

const steps = [
  { stepId: "run:snapshot", label: "snapshot", state: "succeeded", progress: 1, attempts: 1 },
  { stepId: "run:validate", label: "validate", state: "failed", progress: 1, attempts: 3 },
];

test("module registers lazy factory and validation editors behind Blender", () => {
  assert.equal(moduleContribution.manifest.id, "asset-factory");
  assert.deepEqual(moduleContribution.editors.map((editor) => editor.id), ["asset.factory", "asset.validation"]);
  assert.deepEqual(moduleContribution.editors[0].requiredIntegrations, ["blender"]);
});

test("visible permission, offline, loading, empty, and retry failure states", () => {
  assert.equal(buildPipelineEditorState({ ...base, permissionGranted: false }).kind, "permission");
  assert.equal(buildPipelineEditorState({ ...base, integrationConnected: false }).kind, "disconnected");
  assert.equal(buildPipelineEditorState({ ...base, loading: true }).kind, "loading");
  assert.equal(buildPipelineEditorState(base).kind, "empty");
  const failed = buildPipelineEditorState({
    ...base,
    error: { code: "BLENDER_TIMEOUT", message: "Blender 超时", retryable: true },
  });
  assert.equal(failed.kind, "failed");
  if (failed.kind === "failed") assert.equal(failed.action, "重试");
});

test("approval is a planned pause and terminal modes remain visible", () => {
  const approval = buildPipelineEditorState({
    ...base,
    run: { pipelineRunId: "run_1", state: "waiting_approval", executionMode: "planned", steps },
  });
  assert.equal(approval.kind, "approval");
  if (approval.kind === "approval") assert.equal(approval.mode, "planned");

  const rolledBack = buildPipelineEditorState({
    ...base,
    run: {
      pipelineRunId: "run_2",
      state: "rolled_back",
      executionMode: "mock",
      steps,
      errorMessage: "质量门禁失败，已回滚",
    },
  });
  assert.equal(rolledBack.kind, "ready");
  if (rolledBack.kind === "ready") {
    assert.equal(rolledBack.mode, "mock");
    assert.equal(rolledBack.canRetry, true);
    assert.equal(rolledBack.canRollback, true);
  }
});
