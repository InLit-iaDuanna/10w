import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import * as publicApi from "../index.ts";
import { moduleContribution } from "../index.ts";

test("public frontend entry exports the declared contribution and workbench entrypoints", () => {
  assert.deepEqual(Object.keys(publicApi), ["ExportWorkbench", "UnityBuildWorkbench", "loadExportWorkbench", "loadIntegratedWorkbench", "moduleContribution"]);
});

test("module contribution is feature flagged and lazy registers six editors", () => {
  assert.equal(moduleContribution.manifest.id, "build-release");
  assert.equal(moduleContribution.manifest.featureFlag, "build_release");
  assert.equal(moduleContribution.editors.length, 6);
  assert.deepEqual(
    moduleContribution.editors.map((editor) => editor.id),
    [
      "build.export",
      "build.matrix",
      "build.console",
      "release.gates",
      "release.center",
      "release.patch-notes",
    ],
  );
  for (const editor of moduleContribution.editors) {
    assert.equal(typeof editor.load, "function");
    assert.deepEqual(editor.requiredIntegrations, []);
    assert.ok(editor.optionalIntegrations.includes("artifact-store"));
  }
});

test("YAML manifest and frontend IDs remain in parity", () => {
  const moduleYaml = readFileSync(
    new URL("../../../module.yaml", import.meta.url),
    "utf8",
  );
  for (const editor of moduleContribution.editors) {
    assert.match(moduleYaml, new RegExp(`- ${editor.id.replace(".", "\\.")}`));
  }
  for (const command of moduleContribution.commands) {
    assert.match(moduleYaml, new RegExp(`- ${command.id.replaceAll(".", "\\.")}`));
  }
});
