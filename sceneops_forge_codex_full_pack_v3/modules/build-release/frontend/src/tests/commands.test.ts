import assert from "node:assert/strict";
import test from "node:test";

import {
  commandAvailability,
  commandDefinitions,
} from "../commands/definitions.ts";

const context = {
  permissions: new Set(["release:deploy", "release:rollback"]),
  integrations: new Set(["artifact-store"]),
  blockingGateCount: 0,
  approvalScopeValid: true,
};

test("manifest-owned commands are unique", () => {
  const ids = commandDefinitions.map((command) => command.id);
  assert.equal(ids.length, new Set(ids).size);
  assert.equal(ids.length, 10);
});

test("deploy checks permission, integration, gates and exact approval scope", () => {
  assert.deepEqual(commandAvailability("release.deploy", context), { enabled: true });
  assert.match(
    commandAvailability("release.deploy", {
      ...context,
      permissions: new Set(),
    }).reason ?? "",
    /缺少权限/,
  );
  assert.match(
    commandAvailability("release.deploy", {
      ...context,
      integrations: new Set(),
    }).reason ?? "",
    /集成离线/,
  );
  assert.match(
    commandAvailability("release.deploy", {
      ...context,
      blockingGateCount: 1,
    }).reason ?? "",
    /阻断门禁/,
  );
  assert.match(
    commandAvailability("release.deploy", {
      ...context,
      approvalScopeValid: false,
    }).reason ?? "",
    /匹配的审批/,
  );
});

test("rollback execution uses its own permission and approval", () => {
  const available = commandAvailability("release.rollback.execute", context);
  assert.equal(available.enabled, true);
  const noApproval = commandAvailability("release.rollback.execute", {
    ...context,
    approvalScopeValid: false,
  });
  assert.equal(noApproval.enabled, false);
});
