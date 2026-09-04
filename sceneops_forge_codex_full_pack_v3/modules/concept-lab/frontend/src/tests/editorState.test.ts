import assert from "node:assert/strict";
import test from "node:test";

import {
  generationOfflineAvailability,
  resolveEditorAvailability,
  restoreConceptEditorState,
  serializeConceptEditorState,
} from "../index.ts";

test("shows disabled, permission, loading, empty, failed, and ready states", () => {
  assert.equal(resolveEditorAvailability({ moduleEnabled: false, hasReadPermission: true, loading: false }).kind, "disabled");
  assert.equal(resolveEditorAvailability({ moduleEnabled: true, hasReadPermission: false, loading: false }).kind, "permission");
  assert.equal(resolveEditorAvailability({ moduleEnabled: true, hasReadPermission: true, loading: true }).kind, "loading");
  assert.equal(resolveEditorAvailability({ moduleEnabled: true, hasReadPermission: true, loading: false }).kind, "empty");
  assert.equal(resolveEditorAvailability({ moduleEnabled: true, hasReadPermission: true, loading: false, errorMessage: "请求失败" }).kind, "failed");
  assert.equal(resolveEditorAvailability({ moduleEnabled: true, hasReadPermission: true, loading: false, conceptId: "cpt_1" }).kind, "ready");
});

test("offline image generation offers the import path", () => {
  assert.deepEqual(generationOfflineAvailability("未配置模型"), {
    kind: "offline",
    message: "图像生成不可用：未配置模型",
    importCommandId: "concept.reference.import",
  });
});

test("editor-local selection and pinned context round trip", () => {
  const state = {
    selectedVariantIds: ["var_a", "var_b"],
    showRejected: false,
    pinnedConceptId: "cpt_key",
  };
  assert.deepEqual(restoreConceptEditorState(serializeConceptEditorState(state)), state);
  assert.deepEqual(restoreConceptEditorState({ selectedVariantIds: ["ok", 1] }), {
    selectedVariantIds: ["ok"],
    showRejected: true,
    pinnedConceptId: null,
  });
});
