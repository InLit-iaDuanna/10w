import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  designRoomEditorDefinitions,
  moduleContribution,
  moduleManifest,
} from "../index.ts";

test("module.yaml matches the public manifest and declares its module dependencies", async () => {
  const manifestUrl = new URL("../../../module.yaml", import.meta.url);
  const diskManifest = JSON.parse(await readFile(manifestUrl, "utf8"));
  assert.deepEqual(diskManifest, moduleManifest);
  assert.deepEqual(moduleManifest.requires.modules, ["core-kernel", "module-runtime", "project-intake", "ai-run-distiller"]);
  assert.deepEqual(moduleManifest.requires.integrations, []);
});

test("all structured editors lazy-load and every command is registered", async () => {
  assert.deepEqual(
    moduleContribution.commands.map((command) => command.id),
    moduleManifest.contributes.commands,
  );
  assert.deepEqual(
    designRoomEditorDefinitions.map((editor) => editor.id),
    ["project.bible", "design.gdd", "design.feature_spec"],
  );
  for (const editor of designRoomEditorDefinitions) {
    const editorModule = await editor.load();
    assert.equal(typeof editorModule.default, "function");
  }
});
