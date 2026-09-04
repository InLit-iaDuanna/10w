import assert from "node:assert/strict";
import test from "node:test";

import {
  resolveFrontendModuleStates,
  type ModuleManifest,
} from "../manifest.ts";

const manifests: ModuleManifest[] = [
  {
    schema_version: 1,
    id: "core-kernel",
    version: "0.1.0",
    title: "Core Kernel",
    description: "Core",
    status: "active",
    feature_flag: "core_kernel",
    requires: { modules: [], integrations: [], optional_integrations: [] },
    contributes: {
      editors: [],
      commands: [],
      events: [],
      jobs: [],
      workflows: [],
      policy_gates: [],
    },
    permissions: [],
    entrypoints: { frontend: "./frontend/src/index.ts" },
  },
  {
    schema_version: 1,
    id: "example-feature",
    version: "0.1.0",
    title: "Example",
    description: "Example",
    status: "active",
    feature_flag: "example_feature",
    requires: {
      modules: ["core-kernel"],
      integrations: ["required-tool"],
      optional_integrations: ["optional-tool"],
    },
    contributes: {
      editors: [],
      commands: [],
      events: [],
      jobs: [],
      workflows: [],
      policy_gates: [],
    },
    permissions: [],
    entrypoints: { frontend: "./frontend/src/index.ts" },
  },
];

test("feature flag disablement is explicit and blocks dependents", () => {
  const states = resolveFrontendModuleStates(manifests, { core_kernel: false });
  assert.equal(states.get("core-kernel")?.availability, "disabled");
  assert.equal(states.get("example-feature")?.availability, "blocked");
});

test("required integration blocks while optional integration degrades", () => {
  const blocked = resolveFrontendModuleStates(manifests);
  assert.equal(blocked.get("example-feature")?.availability, "blocked");

  const enabled = resolveFrontendModuleStates(
    manifests,
    {},
    new Set(["required-tool"]),
  );
  assert.equal(enabled.get("example-feature")?.availability, "enabled");
  assert.deepEqual(enabled.get("example-feature")?.missingOptionalIntegrations, [
    "optional-tool",
  ]);
});

test("unknown feature flags fail closed", () => {
  assert.throws(
    () => resolveFrontendModuleStates(manifests, { misspelled_flag: false }),
    /UNKNOWN_FEATURE_FLAGS/,
  );
});
