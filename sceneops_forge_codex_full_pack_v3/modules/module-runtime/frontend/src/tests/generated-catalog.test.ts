import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  generatedFrontendModuleIds,
} from "../../../../../apps/web/src/registries/generated-module-catalog.ts";

test("web composition consumes the generated static module catalog", () => {
  const catalog = JSON.parse(
    readFileSync(
      new URL("../../../../../generated/module-catalog.json", import.meta.url),
      "utf8",
    ),
  ) as {
    modules: Array<{ id: string; entrypoints: { frontend?: string } }>;
  };
  const expected = catalog.modules
    .filter((module) => module.entrypoints.frontend)
    .map((module) => module.id);
  assert.deepEqual(generatedFrontendModuleIds, expected);
});
