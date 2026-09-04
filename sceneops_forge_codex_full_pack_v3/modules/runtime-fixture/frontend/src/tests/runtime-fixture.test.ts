import assert from "node:assert/strict";
import test from "node:test";

import { runRuntimeFixture, RuntimeFixtureError } from "../index.ts";

test("fixture success is deterministic and honestly marked mock", () => {
  assert.deepEqual(runRuntimeFixture(), {
    status: "succeeded",
    mode: "mock",
    value: "runtime-fixture-v1",
  });
});

test("fixture failure exposes a stable visible error state", () => {
  assert.throws(
    () => runRuntimeFixture(true),
    (error: unknown) =>
      error instanceof RuntimeFixtureError &&
      error.code === "FIXTURE_REQUESTED_FAILURE" &&
      error.mode === "mock",
  );
});
