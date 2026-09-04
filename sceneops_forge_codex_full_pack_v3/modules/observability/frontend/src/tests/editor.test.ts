import assert from "node:assert/strict";
import test from "node:test";

import { createLogExplorerView } from "../editors/LogExplorerEditor.ts";
import { mockLog } from "../fixtures/logs.mock.ts";
import { defaultLogExplorerState, logExplorerEditor } from "../manifest.ts";
import { exportDiagnosticCommand, searchLogsCommand } from "../commands.ts";

test("ready log editor shows correlation, mode, fields, and artifacts", () => {
  const view = createLogExplorerView({
    phase: "ready",
    filters: { text: "heartbeat" },
    items: [mockLog],
    canExportDiagnostics: true,
  });
  assert.equal(view.status, "ready");
  assert.equal(view.rows[0].modeLabel, "MOCK");
  assert.match(view.rows[0].correlationLabel, /corr_mock/);
  assert.match(view.rows[0].correlationLabel, /evt_mock/);
  assert.deepEqual(view.rows[0].fields, ["code=HEARTBEAT_DELAYED", "duration_ms=12000"]);
  assert.equal(view.rows[0].artifacts[0].artifactId, "art_mock_log_01");
  assert.equal(view.actions[1].available, true);
});

test("failure, disconnected, permission, loading, and empty states remain explicit", () => {
  const phases = ["failed", "disconnected", "permission_denied", "loading", "empty"] as const;
  for (const phase of phases) {
    const view = createLogExplorerView({
      ...defaultLogExplorerState,
      phase,
      errorMessage: phase === "failed" ? "查询失败：服务不可用。" : undefined,
    });
    assert.equal(view.status, phase);
    assert.notEqual(view.banner, "");
  }
  const denied = createLogExplorerView({ ...defaultLogExplorerState, phase: "permission_denied" });
  assert.equal(denied.actions[0].available, false);
  assert.match(denied.actions[0].unavailableReason ?? "", /权限/);
});

test("editor registration is lazy and restores only serializable filters", async () => {
  assert.equal(logExplorerEditor.id, "observability.logs");
  assert.equal(logExplorerEditor.defaultPlacement, "bottom");
  const restored = logExplorerEditor.restoreState({ filters: { text: "build", sourceTool: "unity" } });
  assert.equal(restored.filters.text, "build");
  const loaded = await logExplorerEditor.load();
  assert.equal(typeof loaded.default, "function");
});

test("typed commands expose permission and project preconditions", () => {
  const denied = searchLogsCommand.canExecute({ permissions: new Set() }, { text: "" });
  const searchWithoutProject = searchLogsCommand.canExecute(
    { permissions: new Set(["observability:read"]) },
    { text: "" },
  );
  const noProject = exportDiagnosticCommand.canExecute(
    { permissions: new Set(["observability:export"]) },
    {},
  );
  const allowed = exportDiagnosticCommand.canExecute(
    { projectId: "prj_1", permissions: new Set(["observability:export"]) },
    {},
  );
  assert.equal(denied.available, false);
  assert.match(denied.reason ?? "", /权限/);
  assert.equal(searchWithoutProject.available, false);
  assert.match(searchWithoutProject.reason ?? "", /项目/);
  assert.equal(noProject.available, false);
  assert.match(noProject.reason ?? "", /项目/);
  assert.equal(allowed.available, true);
});
