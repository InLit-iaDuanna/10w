import assert from "node:assert/strict";
import test from "node:test";

import {
  defaultReviewEditorState,
  restoreReviewEditorState,
  serializeReviewEditorState,
} from "../state/reviewEditorState.ts";


test("review editor state serializes follow-global context", () => {
  const restored = restoreReviewEditorState(
    serializeReviewEditorState(defaultReviewEditorState),
  );

  assert.deepEqual(restored, defaultReviewEditorState);
});

test("review editor preserves pinned revision for side-by-side comparison", () => {
  const restored = restoreReviewEditorState({
    schemaVersion: 1,
    selectedLayer: "visual",
    contextBinding: {
      mode: "pinned",
      projectId: "project_home",
      reviewId: "review_1",
      reviewRevisionId: "reviewrev_1",
    },
    expectedMode: "cached",
  });

  assert.equal(restored.contextBinding.mode, "pinned");
  if (restored.contextBinding.mode === "pinned") {
    assert.equal(restored.contextBinding.reviewRevisionId, "reviewrev_1");
  }
  assert.equal(restored.selectedLayer, "visual");
  assert.equal(restored.expectedMode, "cached");
});

test("invalid or future editor state is rejected visibly", () => {
  assert.throws(
    () => restoreReviewEditorState({ schemaVersion: 2 }),
    /REVIEW_STATE_SCHEMA_UNSUPPORTED/,
  );
  assert.throws(
    () => restoreReviewEditorState({
      schemaVersion: 1,
      selectedLayer: "magic",
      contextBinding: { mode: "follow-global" },
      expectedMode: null,
    }),
    /REVIEW_STATE_INVALID/,
  );
});
