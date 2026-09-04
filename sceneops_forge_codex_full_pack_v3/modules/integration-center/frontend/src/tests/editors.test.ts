import assert from "node:assert/strict";
import test from "node:test";

import { createIntegrationHealthEditorView } from "../editors/IntegrationHealthEditor.ts";
import { createWorkerMonitorEditorView } from "../editors/WorkerMonitorEditor.ts";
import { mockHealth, mockLogs, mockWorkers } from "../fixtures/health.mock.ts";
import { openLogsCommand, retryJobCommand } from "../commands.ts";
import {
  defaultHealthEditorState,
  defaultWorkerEditorState,
  integrationHealthEditor,
  workerMonitorEditor,
} from "../manifest.ts";

test("health editor shows versions, capabilities, reason, logs, and honest mode", () => {
  const view = createIntegrationHealthEditorView({
    phase: "ready",
    integrations: mockHealth,
    recentLogs: mockLogs,
    searchText: "",
  });
  assert.equal(view.rows.length, 2);
  assert.equal(view.rows[0].modeLabel, "MOCK");
  assert.match(view.rows[0].explanation, /不能启用 Live/);
  assert.match(view.rows[1].versionLabel, /2022\.3\.1/);
  assert.match(view.rows[1].capabilityLabel, /project\.scan/);
  assert.match(view.rows[1].explanation, /build\.run/);
  assert.equal(view.rows[1].logs[0].correlationId, "corr_mock_01");
  assert.equal(view.rows[1].actions[0].available, false);
  assert.match(view.rows[1].actions[0].unavailableReason ?? "", /不兼容/);
});

test("health editor exposes every required loading and failure state", () => {
  const phases = ["loading", "empty", "failed", "disconnected", "permission_denied"] as const;
  for (const phase of phases) {
    const view = createIntegrationHealthEditorView({ ...defaultHealthEditorState, phase });
    assert.equal(view.status, phase);
    assert.notEqual(view.banner, "");
  }
});

test("worker monitor never exposes recovery commands for non-live evidence", () => {
  const view = createWorkerMonitorEditorView({
    phase: "ready",
    workers: mockWorkers,
    recentLogs: mockLogs,
    searchText: "",
  });
  const retry = view.rows[0].recoveryActions.find((action) => action.commandId === "job.retry");
  const resume = view.rows[0].recoveryActions.find((action) => action.commandId === "job.resume");
  assert.equal(retry?.available, false);
  assert.match(retry?.unavailableReason ?? "", /Live Worker/);
  assert.equal(resume?.available, false);
  assert.match(resume?.unavailableReason ?? "", /Live Worker/);
  assert.match(view.rows[0].jobLabel, /corr_mock_01/);
  assert.equal(view.rows[0].modeLabel, "MOCK");
  assert.match(view.rows[0].versionLabel, /0\.1\.0/);
  assert.match(view.rows[0].capabilityLabel, /build\.run/);
  assert.match(view.rows[0].freshnessLabel, /已过期/);
});

test("worker monitor disables control for expired live evidence", () => {
  const view = createWorkerMonitorEditorView({
    phase: "ready",
    workers: [{ ...mockWorkers[0], mode: "live", isCurrent: false }],
    recentLogs: [],
    searchText: "",
  });
  const retry = view.rows[0].recoveryActions.find((action) => action.commandId === "job.retry");
  assert.equal(retry?.available, false);
  assert.match(retry?.unavailableReason ?? "", /心跳证据已过期/);
});

test("both editors register lazily and restore only local filters", async () => {
  assert.equal(integrationHealthEditor.id, "integration.health");
  assert.equal(workerMonitorEditor.id, "worker.monitor");
  const restored = integrationHealthEditor.restoreState({ selectedIntegrationId: "unity", searchText: "build" });
  assert.equal(restored.selectedIntegrationId, "unity");
  assert.equal(restored.integrations.length, 0);
  const workerRestored = workerMonitorEditor.restoreState({ selectedWorkerId: "worker_1", searchText: "unity" });
  assert.equal(workerRestored.selectedWorkerId, "worker_1");
  assert.equal(workerRestored.workers.length, 0);
  const [healthModule, workerModule] = await Promise.all([
    integrationHealthEditor.load(),
    workerMonitorEditor.load(),
  ]);
  assert.equal(typeof healthModule.default, "function");
  assert.equal(typeof workerModule.default, "function");
});

test("typed commands use permissions, context identity, and the shared open-editor action", async () => {
  const input = {
    jobId: "job_1",
    attemptId: "attempt_2",
    idempotencyKey: "key_1",
    context: {
      projectId: "prj_1",
      runId: "run_1",
      jobId: "job_other",
      correlationId: "corr_1",
      causationId: "cmd_1",
    },
  };
  const mismatch = retryJobCommand.canExecute(
    { permissions: new Set(["job:operate"]), projectId: "prj_1" },
    input,
  );
  assert.equal(mismatch.available, false);
  assert.match(mismatch.reason ?? "", /jobId/);

  const open = await openLogsCommand.execute(
    {} as never,
    { permissions: new Set(["observability:read"]), projectId: "prj_1" },
    { integrationId: "unity", correlationId: "corr_1" },
    new AbortController().signal,
  );
  assert.equal(open.type, "workbench.open_editor");
  assert.equal(open.editorId, "observability.logs");
  assert.equal(open.requireConfirmation, true);
});
