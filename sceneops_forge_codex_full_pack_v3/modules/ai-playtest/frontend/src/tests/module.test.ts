import assert from "node:assert/strict";
import test from "node:test";
import { renderToStaticMarkup } from "react-dom/server";

import { playtestCommands, runAvailability } from "../commands/definitions.ts";
import {
  defaultPlaytestEditorState,
  editorStatus,
  restorePlaytestEditorState,
  serializePlaytestEditorState,
} from "../editor-state.ts";
import { playtestEditors } from "../editor-definitions.ts";
import { moduleContribution } from "../index.ts";
import { manifest } from "../manifest.ts";
import {
  issueBrowserViewModel,
  regressionViewModel,
  stepLogViewModel,
} from "../view-models.ts";
import type {
  CommandAvailabilityContext,
  PlaytestEditorProps,
  PlaytestReadModel,
  RunPlaytestInput,
  WorkbenchCommandDefinition,
} from "../types.ts";

const context: CommandAvailabilityContext = {
  projectId: "project.hero",
  branchId: "branch.main",
  sceneId: "scene.home",
  selectedSceneObjectIds: [],
  selectedAssetIds: [],
  activeFeatureId: null,
  activeTaskId: null,
  activeChangeSetId: null,
  activeRenderJobId: null,
  activeBuildId: "build.hero.before",
  activePlaytestRunId: "run.hero.before",
  activeIssueId: null,
  moduleEnabled: true,
  grantedPermissions: [
    "playtest:read",
    "playtest:run",
    "playtest:cancel",
    "issue:read",
    "issue:write",
    "changeset:propose",
  ],
  requestedMode: "mock",
  playtestRunnerAvailable: false,
  cachedPlaytestAvailable: false,
};

const readModel: PlaytestReadModel = {
  surfaceState: "ready",
  executionMode: "mock",
  runId: "run.hero.before",
  status: "failed",
  objective: "拾取钥匙并打开家门",
  agentMode: "goal_driven",
  actionBounds: { maxSteps: 8, maxDurationMs: 20_000, actionTimeoutMs: 2_000 },
  buildId: "build.hero.before",
  goals: [{ goalId: "goal.key-door", label: "打开家门", state: "in_progress", value: 0.6 }],
  steps: [{
    stepIndex: 0,
    occurredAt: "2026-09-04T04:00:00Z",
    actionId: "action.door.interact",
    actionLabel: "用钥匙开门",
    outcome: "failed",
    targetSceneOpsId: "sceneops.home-door",
    position: [5, 0, 0],
    camera: { position: [5, 1.6, -2], rotationEulerDegrees: [0, 0, 0] },
    gameState: { has_key: true, door_open: false },
    goals: [{ goalId: "goal.key-door", label: "打开家门", state: "in_progress", value: 0.6 }],
    availableActionIds: ["action.door.interact"],
    evidenceArtifactIds: ["artifact.screenshot.hero.0"],
    signalKinds: ["collider_error"],
  }],
  issues: [{
    issueId: "issue.hero.door",
    title: "门交互碰撞体阻挡",
    severity: "error",
    failureKind: "collider_error",
    backpinStatus: "rejected",
    backpinConfidence: 0.91,
    backpinTargetId: "component.home-door-interaction",
    backpinReasons: ["同构建证据与稳定目标一致"],
    backpinAlternatives: ["component.home-door-collider"],
    backpinReviewedBy: "user.qa-reviewer",
    stepIndex: 0,
    limitationLabels: ["回钉已由认证用户人工拒绝；原始证据仍可恢复。"],
  }],
  regressionStatus: "improved",
  exactConfiguration: true,
  baselineBuildId: "build.hero.before",
  candidateBuildId: "build.hero.after",
  newIssueIds: [],
  resolvedIssueIds: ["issue.hero.door"],
  persistentIssueIds: [],
  regressionMetrics: [{
    metricId: "goal_completion",
    baseline: 0,
    candidate: 1,
    outcome: "improved",
    unit: "ratio",
  }],
  limitationLabels: ["AI Playtest 不能替代真人体验、可用性或偏好测试。"],
};

function editorProps(model: PlaytestReadModel = readModel): PlaytestEditorProps {
  return {
    instanceId: "editor.fixture",
    contextBinding: { mode: "follow-global" },
    localState: {
      ...defaultPlaytestEditorState,
      comparisonId: "comparison.hero",
      baselineRunId: "run.hero.before",
      candidateRunId: "run.hero.after",
    },
    updateLocalState: () => undefined,
    commands: { execute: async () => undefined },
    events: { publish: async () => undefined },
    close: () => undefined,
    setTitle: () => undefined,
    readModel: model,
  };
}

test("registers and lazy-loads all six contract-complete editors", async () => {
  assert.equal(manifest.id, "ai-playtest");
  assert.equal(playtestEditors.length, 6);
  for (const editor of playtestEditors) {
    assert.equal(editor.supportsContextBinding, true);
    assert.equal(typeof editor.serializeState, "function");
    assert.equal(typeof editor.restoreState, "function");
    assert.ok(editor.supportedStates.includes("permission_denied"));
    const loaded = await editor.load();
    assert.equal(typeof loaded.default, "function");
    assert.ok(loaded.default(editorProps()));
  }
  assert.equal(moduleContribution.workspacePresets[0].userInitiatedOnly, true);
});

test("execution mode comes from server read model and protected states hide domain data", async () => {
  const agent = await playtestEditors[1].load();
  const offline = { ...readModel, surfaceState: "offline" as const, executionMode: "blocked" as const };
  const html = renderToStaticMarkup(agent.default(editorProps(offline)) as never);
  assert.match(html, /BLOCKED/);
  assert.doesNotMatch(html, /拾取钥匙并打开家门/);
  assert.doesNotMatch(html, /运行 TestCase/);
  assert.match(editorStatus("ready", "mock").modeLabel, /^MOCK/);
});

test("local state round-trips view preferences but cannot override execution truth", () => {
  const state = {
    ...defaultPlaytestEditorState,
    selectedIssueId: "issue.hero.door",
    trajectoryZoom: 1.5,
  };
  const encoded = serializePlaytestEditorState(state);
  assert.deepEqual(restorePlaytestEditorState(encoded), state);
  assert.equal("mode" in state, false);
  assert.throws(() => restorePlaytestEditorState(null));
  assert.throws(() => restorePlaytestEditorState({
    followLatest: true,
    trajectoryZoom: 1,
    executionMode: "live",
  }));
  assert.throws(() => restorePlaytestEditorState({
    followLatest: true,
    trajectoryZoom: 0,
  }));
  assert.throws(() => restorePlaytestEditorState({
    followLatest: true,
    trajectoryZoom: 1,
    selectedStepIndex: 1.5,
  }));
  assert.throws(() => restorePlaytestEditorState({
    followLatest: true,
    trajectoryZoom: 1,
    baselineRunId: "r".repeat(97),
  }));
});

test("command definitions validate, gate, and delegate through one implementation", async () => {
  const run = playtestCommands[0] as WorkbenchCommandDefinition<RunPlaytestInput, unknown>;
  const input = run.inputSchema.parse({
    runId: "run.hero",
    testCaseId: "test.hero",
    buildId: "build.hero",
    executionMode: "mock",
    replayActionIds: [],
  });
  assert.equal(run.canExecute(context, input).available, true);
  assert.equal(
    run.canExecute(context, { ...input, executionMode: "live" }).code,
    "INTEGRATION_OFFLINE",
  );
  assert.throws(() => run.inputSchema.parse({ ...input, executionMode: "planned" }));
  assert.throws(() => run.inputSchema.parse({ ...input, runId: "r".repeat(97) }));
  const calls: unknown[] = [];
  await run.execute({
    playtestApi: {
      run: async (value) => calls.push(value),
      cancel: async () => undefined,
      restoreIssue: async () => undefined,
      beginChangeProposal: async () => undefined,
      reviewBackpin: async () => undefined,
      compare: async () => undefined,
    },
  }, input);
  assert.deepEqual(calls, [input]);
});

test("mode, permission, and module gates remain explicit", () => {
  assert.equal(runAvailability({ ...context, requestedMode: "live" }).code, "INTEGRATION_OFFLINE");
  assert.equal(runAvailability({ ...context, requestedMode: "mock" }).available, true);
  assert.equal(
    runAvailability({ ...context, requestedMode: "cached" }).code,
    "CACHED_RESULT_UNAVAILABLE",
  );
  assert.equal(runAvailability({ ...context, moduleEnabled: false }).code, "MODULE_DISABLED");
  assert.equal(runAvailability({ ...context, grantedPermissions: [] }).code, "PERMISSION_DENIED");
});

test("editor view models expose step evidence, rejected backpin restoration, and exact regression", () => {
  const steps = stepLogViewModel(readModel);
  assert.deepEqual(steps[0].evidenceArtifactIds, ["artifact.screenshot.hero.0"]);
  const issues = issueBrowserViewModel(readModel);
  assert.equal(issues[0].canRestore, true);
  assert.equal(issues[0].canProposeChange, false);
  const regression = regressionViewModel(readModel);
  assert.equal(regression.exactConfiguration, true);
  assert.deepEqual(regression.resolvedIssueIds, ["issue.hero.door"]);
  assert.match(readModel.limitationLabels[0], /不能替代真人/);
});

test("issue browser renders reviewer state and issue limitation labels", async () => {
  const issueBrowser = await playtestEditors[4].load();
  const html = renderToStaticMarkup(issueBrowser.default(editorProps()) as never);
  assert.match(html, /审核人：user.qa-reviewer/);
  assert.match(html, /人工拒绝/);
});

test("buttons and chat share the registered command ids", () => {
  assert.deepEqual(
    playtestCommands.map((command) => command.id),
    [
      "playtest.run",
      "playtest.cancel",
      "playtest.issue.open-backpin",
      "playtest.issue.review-backpin",
      "playtest.changeset.propose",
      "playtest.regression.compare",
    ],
  );
});
