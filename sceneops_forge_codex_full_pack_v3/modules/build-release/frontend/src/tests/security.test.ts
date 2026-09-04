import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const sourceRoot = new URL("../", import.meta.url);

test("frontend module does not call tools, filesystem or network directly", () => {
  const files = [
    "index.ts",
    "commands/definitions.ts",
    "editors/definitions.ts",
    "state/editor-state.ts",
  ];
  const combined = files
    .map((file) => readFileSync(new URL(file, sourceRoot), "utf8"))
    .join("\n");
  for (const forbidden of ["fetch(", "XMLHttpRequest", "child_process", "subprocess", "UnityEditor", "DockviewApi"])
    assert.equal(combined.includes(forbidden), false, forbidden);
});
