import assert from "node:assert/strict";
import test from "node:test";

import { moduleContribution } from "../index.ts";

test("registers both concept editors and every public command", () => {
  assert.equal(moduleContribution.manifest.id, "concept-lab");
  assert.deepEqual(
    moduleContribution.editors.map((editor) => editor.id),
    ["concept.moodboard", "concept.style_bible"],
  );
  assert.equal(new Set(moduleContribution.commands.map((command) => command.id)).size, 14);
  assert.ok(moduleContribution.commands.some((command) => command.id === "concept.asset_spec_draft.compile"));
});

test("declares image generation as optional", () => {
  const generate = moduleContribution.commands.find(
    (command) => command.id === "concept.variant.generate",
  );
  assert.deepEqual(generate?.requiredIntegrations, []);
  assert.deepEqual(generate?.optionalIntegrations, ["image-generation"]);
});

test("review and asset-draft commands declare their policy permissions", () => {
  const review = moduleContribution.commands.find(
    (command) => command.id === "concept.variant.review",
  );
  const compile = moduleContribution.commands.find(
    (command) => command.id === "concept.asset_spec_draft.compile",
  );
  assert.deepEqual(review?.requiredPermissions, ["concept:review"]);
  assert.deepEqual(compile?.requiredPermissions, ["concept:read", "asset-spec:draft"]);
});
