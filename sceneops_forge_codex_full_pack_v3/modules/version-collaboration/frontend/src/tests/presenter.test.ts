import assert from "node:assert/strict";
import test from "node:test";

import type { ReviewSession } from "../generated/api-types.ts";
import { modeLabel, presentReview } from "../components/reviewPresenter.ts";


test("editor exposes loading, empty, offline, permission, and failure states", () => {
  const baseline = {
    loading: false,
    hasPermission: true,
    gitConnected: true,
    review: null,
    errorCode: null,
  };

  assert.equal(presentReview({ ...baseline, loading: true }).state, "loading");
  assert.equal(presentReview(baseline).state, "empty");
  assert.equal(presentReview({ ...baseline, gitConnected: false }).state, "offline");
  assert.equal(presentReview({ ...baseline, hasPermission: false }).state, "permission");
  const failed = presentReview({ ...baseline, errorCode: "STALE_BASE" });
  assert.equal(failed.state, "failed");
  assert.match(failed.message, /基线已变化/);
});

test("success state preserves explicit execution mode and conflicts", () => {
  const review = {
    title: "钥匙开门评审",
    mode: "mock",
    diff: {
      diff_bundle_id: "diff_1",
      conflicts: [{ message: "二进制资产缺少锁" }],
    },
  } as unknown as ReviewSession;

  const view = presentReview({
    loading: false,
    hasPermission: true,
    gitConnected: true,
    review,
    errorCode: null,
  });

  assert.equal(view.state, "success");
  assert.equal(view.mode, "mock");
  assert.match(view.modeLabel, /^MOCK/);
  assert.deepEqual(view.conflictMessages, ["二进制资产缺少锁"]);

  const offline = presentReview({
    loading: false,
    hasPermission: true,
    gitConnected: false,
    review,
    errorCode: null,
  });
  assert.equal(offline.state, "success");
  assert.match(offline.message, /离线读取已封存差异/);
});

test("all truthfulness labels include text, not color alone", () => {
  for (const mode of ["live", "cached", "mock", "planned", "blocked"] as const) {
    assert.match(modeLabel(mode), new RegExp(`^${mode.toUpperCase()}`));
  }
});
