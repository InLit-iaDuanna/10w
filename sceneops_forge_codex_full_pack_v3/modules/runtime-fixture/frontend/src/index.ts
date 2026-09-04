import type { ModuleContribution } from "../../../module-runtime/frontend/src/index.ts";
import { generatedModuleManifest } from "./generated/module-manifest.ts";

export interface RuntimeFixtureSuccess {
  readonly status: "succeeded";
  readonly mode: "mock";
  readonly value: "runtime-fixture-v1";
}

export class RuntimeFixtureError extends Error {
  readonly code = "FIXTURE_REQUESTED_FAILURE";
  readonly status = "failed";
  readonly mode = "mock";
  readonly retryable = false;

  constructor() {
    super("Fixture 请求失败。");
  }
}

export function runRuntimeFixture(shouldFail = false): RuntimeFixtureSuccess {
  if (shouldFail) {
    throw new RuntimeFixtureError();
  }
  return {
    status: "succeeded",
    mode: "mock",
    value: "runtime-fixture-v1",
  };
}

export const moduleContribution = {
  manifest: generatedModuleManifest,
  editors: [{ id: "runtime.fixture", title: "运行时 Fixture" }],
  commands: [{ id: "runtime.fixture.run", execute: runRuntimeFixture }],
  events: ["runtime.fixture.completed@1"],
  jobs: ["runtime.fixture.execute"],
} as const satisfies ModuleContribution;
