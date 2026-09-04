import assert from "node:assert/strict";
import test from "node:test";

import type { VersionCollaborationApi } from "../api.ts";
import type { CommandExecutionContext } from "../contracts.ts";
import { moduleContribution, reviewKeys } from "../index.ts";


test("module registers three lazy review editors and an opt-in Review workspace", () => {
  assert.equal(moduleContribution.manifest.id, "version-collaboration");
  assert.deepEqual(
    moduleContribution.editors.map((editor) => editor.id),
    ["review.version-diff", "review.session", "review.activity"],
  );
  assert.equal(moduleContribution.workspacePresets[0].id, "review");
  assert.equal(moduleContribution.workspacePresets[0].activateOnFreshLaunch, false);
  assert.equal(moduleContribution.workspacePresets[0].areas.length, 3);
  assert.ok(moduleContribution.editors.every((editor) => editor.supportsContextBinding));
  assert.ok(moduleContribution.editors.every((editor) => editor.serializeState));
  assert.ok(moduleContribution.editors.every((editor) => editor.restoreState));
});

test("commands share typed handlers and surface permission/integration failures", async () => {
  const calls: unknown[] = [];
  const api = new Proxy({}, {
    get: (_target, property) => async (...args: unknown[]) => {
      calls.push([property, ...args]);
      return { ok: true };
    },
  }) as VersionCollaborationApi;
  const fullContext: CommandExecutionContext = {
    permissions: new Set(["review:read", "review:create", "review:comment", "review:assign", "review:approve", "version:lock", "version:rollback"]),
    integrations: new Set(["git", "git-lfs"]),
    versionCollaborationApi: api,
  };
  const create = moduleContribution.commands.find((command) => command.id === "review.session.create");
  assert.ok(create);
  assert.equal(create.canExecute(fullContext).available, true);
  await create.execute(fullContext, {
    project_id: "project_home",
    repository_id: "repository_home",
    title: "评审",
    base_commit: "1".repeat(40),
    target_commit: "2".repeat(40),
  });
  assert.equal((calls[0] as unknown[])[0], "createReview");

  const unavailable = create.canExecute({ permissions: new Set(), integrations: new Set() });
  assert.equal(unavailable.available, false);
  assert.match(unavailable.reason ?? "", /^MISSING_PERMISSION:/);
});

test("command parser rejects missing required fields before API execution", () => {
  const command = moduleContribution.commands.find((item) => item.id === "review.rollback.execute");
  assert.ok(command);
  assert.throws(
    () => command.inputSchema.parse({ proposal_id: "rollback_1" }),
  );
});

test("query keys remain module-owned and deterministic", () => {
  assert.deepEqual(reviewKeys.detail("review_1"), [
    "version-collaboration",
    "reviews",
    "detail",
    "review_1",
  ]);
});
