import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  generatedFrontendModuleIds, generatedFrontendModuleCatalog,
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


test("frontend catalog binds complete canonical manifests", () => {
  const catalog = JSON.parse(readFileSync(
    new URL("../../../../../generated/module-catalog.json", import.meta.url), "utf8",
  ));
  for (const contribution of generatedFrontendModuleCatalog) {
    const canonical = catalog.modules.find((module: { id: string }) => module.id === contribution.manifest.id);
    const { default_enabled, missing_integration_fields, ...manifest } = canonical;
    assert.deepEqual(contribution.manifest, manifest);
  }
});
