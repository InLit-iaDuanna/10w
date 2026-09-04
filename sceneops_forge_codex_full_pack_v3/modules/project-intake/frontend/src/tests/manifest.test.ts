import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  moduleContribution,
  moduleManifest,
  projectIntakeEditorDefinition,
} from "../index.ts";

test("module.yaml is valid JSON-form YAML and matches the public manifest", async () => {
  const manifestUrl = new URL("../../../module.yaml", import.meta.url);
  const diskManifest = JSON.parse(await readFile(manifestUrl, "utf8"));
  assert.deepEqual(diskManifest, moduleManifest);
  assert.equal(moduleManifest.schema_version, 1);
  assert.equal(moduleManifest.feature_flag, "project_intake");
  assert.deepEqual(moduleManifest.requires.modules, ["core-kernel", "module-runtime"]);
});

test("public contribution registers one lazy editor and every declared command", async () => {
  assert.equal(moduleContribution.editors[0]?.id, "project.intake");
  assert.deepEqual(
    moduleContribution.commands.map((command) => command.id),
    moduleManifest.contributes.commands,
  );
  const editorModule = await projectIntakeEditorDefinition.load();
  assert.equal(typeof editorModule.default, "function");
});
