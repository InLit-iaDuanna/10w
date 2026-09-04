import assert from "node:assert/strict";
import test from "node:test";

import {
  MODE_PRESENTATION,
  buildEditorViewModel,
  restoreEditorState,
  serializeEditorState,
  type ExecutionMode,
} from "../state/editor-state.ts";
import {
  cachedLabelContractFixture,
  deterministicEditorStates,
} from "../fixtures/editor-fixtures.ts";

test("all loading, empty, success, failure, offline and permission states are visible", () => {
  for (const snapshot of Object.values(deterministicEditorStates)) {
    const view = buildEditorViewModel(snapshot);
    assert.ok(view.stateLabel.length > 0);
    assert.ok(view.modeLabel.length > 0);
    assert.ok(view.headline.length > 0);
  }
  const failure = buildEditorViewModel(deterministicEditorStates.failed);
  assert.match(failure.headline, /DEPLOYMENT_ADAPTER_FAILED/);
  assert.equal(failure.action?.commandId, "release.deploy.retry");
  const offline = buildEditorViewModel(deterministicEditorStates.offline);
  assert.equal(offline.action?.commandId, "integration.open");
});

test("all five truthfulness modes have icon and text labels", () => {
  const modes: ExecutionMode[] = ["live", "cached", "mock", "planned", "blocked"];
  for (const mode of modes) {
    assert.ok(MODE_PRESENTATION[mode].icon);
    assert.match(MODE_PRESENTATION[mode].label, new RegExp(mode, "i"));
  }
  assert.equal(cachedLabelContractFixture.fixtureMode, "mock");
  assert.equal(cachedLabelContractFixture.recordMode, "cached");
  assert.ok(cachedLabelContractFixture.originLiveRunId);
});

test("blocking gates disable release with a user-facing reason", () => {
  const view = buildEditorViewModel({
    view: "ready",
    mode: "live",
    headline: "候选已评估",
    blockingGateCount: 2,
  });
  assert.equal(view.action?.commandId, "release.deploy");
  assert.equal(view.action?.disabled, true);
  assert.match(view.action?.reason ?? "", /2 个阻断门禁/);
});

test("serializable local state round-trips and rejects server entities", () => {
  const restored = restoreEditorState({
    selectedId: "candidate.one",
    filter: "failed",
    followTail: false,
    expandedIds: ["gate.asset", 123],
    activeTab: "history",
    candidate: { secret: "server entity must not persist" },
  });
  assert.deepEqual(restored.expandedIds, ["gate.asset"]);
  assert.equal("candidate" in restored, false);
  assert.deepEqual(serializeEditorState(restored), restored);
  assert.deepEqual(restoreEditorState(null).expandedIds, []);
});
