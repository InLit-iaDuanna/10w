import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { blockedFrontendContributions, moduleContribution } from "../index.ts";

test("public entry keeps unavailable React editors and core commands blocked", () => {
  assert.equal(moduleContribution.manifest.id, "production-planner");
  assert.deepEqual(moduleContribution.editors, []);
  assert.deepEqual(moduleContribution.commands, []);
  assert.equal(moduleContribution.manifest.frontendIntegrationStatus, "blocked");
  assert.deepEqual(
    blockedFrontendContributions.editors.map((editor) => editor.id),
    ["production.plan", "production.task"],
  );
  assert.deepEqual(
    blockedFrontendContributions.commands.map((command) => command.id),
    ["production.plan.create", "production.task.open"],
  );
});

test("frontend contains no module-specific transport or production-tool execution", async () => {
  const files = [
    "../ports.ts",
    "../commands/createProductionPlan.ts",
    "../commands/openTask.ts",
    "../editors/editorState.ts",
  ];
  const source = await Promise.all(files.map((path) => readFile(new URL(path, import.meta.url), "utf8")));
  const joined = source.join("\n");
  assert.doesNotMatch(joined, /\bfetch\s*\(/);
  assert.doesNotMatch(joined, /child_process|execSync|spawnSync/);
  assert.doesNotMatch(joined, /blender|unity|comfyui|git\s/i);
});
