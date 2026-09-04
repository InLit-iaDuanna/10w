import assert from "node:assert/strict";
import test from "node:test";

import {
  commandDefinitions,
  editorDefinitions,
  executionModeLabels,
  integrationState,
  moduleContribution,
} from "../index.ts";

test("registers every manifest editor and command without direct tool execution", () => {
  assert.equal(editorDefinitions.length, 5);
  assert.equal(commandDefinitions.length, 16);
  assert.equal(moduleContribution.manifest.id, "engine-unity");
  assert.equal(commandDefinitions.some(({ id }) => id.includes("csharp")), false);
  assert.equal(commandDefinitions.some(({ id }) => id.includes("shell")), false);
});

test("all editors are lazy and require the Unity integration", async () => {
  for (const definition of editorDefinitions) {
    assert.deepEqual(definition.requiredIntegrations, ["unity"]);
    assert.equal(typeof definition.load, "function");
  }
  const loaded = await editorDefinitions[0].load();
  assert.equal(typeof loaded.default, "function");
});

test("disconnected and disabled states are visible and blocked", () => {
  const disconnected = integrationState("live", {
    enabled: true,
    permitted: true,
    connected: false,
  });
  assert.equal(disconnected.kind, "offline");
  assert.equal(disconnected.mode, "blocked");
  assert.equal(disconnected.retryCommandId, "unity.health");

  const disabled = integrationState("mock", { enabled: false });
  assert.equal(disabled.kind, "offline");
  assert.equal(disabled.mode, "blocked");
});

test("retryable failures expose retry while terminal failures do not", () => {
  const retryable = integrationState("live", {
    connected: true,
    failure: { code: "UNITY_TIMEOUT", message: "构建超时", retryable: true },
  });
  const terminal = integrationState("live", {
    connected: true,
    failure: { code: "UNITY_COMPILE_FAILED", message: "编译失败", retryable: false },
  });
  assert.equal(retryable.retryCommandId, "run.retry");
  assert.equal(terminal.retryCommandId, undefined);
  assert.match(terminal.message, /UNITY_COMPILE_FAILED/);
});

test("execution labels distinguish all truthful modes", () => {
  assert.deepEqual(Object.keys(executionModeLabels).sort(), [
    "blocked",
    "cached",
    "live",
    "mock",
    "planned",
  ]);
  assert.notEqual(executionModeLabels.live, executionModeLabels.mock);
  assert.notEqual(executionModeLabels.cached, executionModeLabels.live);
});

test("editor state restores invalid layouts to a deterministic default", () => {
  const restored = editorDefinitions[0].restoreState({ schemaVersion: 99 });
  assert.deepEqual(restored, {
    schemaVersion: 1,
    selectedBuildId: null,
    selectedSceneOpsId: null,
    followGlobalContext: true,
    logLevel: "info",
  });
});
