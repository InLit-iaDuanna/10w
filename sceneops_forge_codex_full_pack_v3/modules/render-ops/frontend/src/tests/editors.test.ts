import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { moduleContribution, renderEditors } from "../manifest.ts";
import { buildPresentation, executionModeLabel } from "../presentation.ts";
import {
  applyServerEditorState,
  defaultEditorState,
  restoreEditorState,
  serializeEditorState,
} from "../state.ts";
import type { EditorStatus, ExecutionMode, RenderEditorLocalState } from "../contracts.ts";

const expectedEditors = [
  "render.viewer",
  "render.aov-viewer",
  "render.recipe",
  "render.queue",
  "render.comparison",
  "render.provenance",
];

test("registers every Render Ops editor with permissions and lazy loaders", () => {
  assert.deepEqual(renderEditors.map((editor) => editor.id), expectedEditors);
  for (const editor of renderEditors) {
    assert.equal(typeof editor.load, "function");
    assert.deepEqual(editor.requiredPermissions, ["render:read"]);
    assert.deepEqual(editor.optionalIntegrations, ["comfyui", "blender", "unity"]);
    assert.ok(editor.minWidth >= 320);
    assert.ok(editor.minHeight >= 220);
  }
});

test("module respects its feature flag and Render preset is opt-in", () => {
  assert.equal(moduleContribution.isEnabled({ render_ops: true }), true);
  assert.equal(moduleContribution.isEnabled({ render_ops: false }), false);
  assert.equal(moduleContribution.workspacePresets[0].requiresConfirmation, true);
});

test("all execution modes have explicit non-color labels", () => {
  const modes: ExecutionMode[] = ["live", "cached", "mock", "planned", "blocked"];
  for (const mode of modes) assert.match(executionModeLabel(mode), new RegExp(mode, "i"));
});

test("loading, empty, success, failure, offline, and permission states are visible", () => {
  const statuses: EditorStatus[] = [
    "loading",
    "empty",
    "ready",
    "failed",
    "offline",
    "permission-denied",
  ];
  for (const status of statuses) {
    const state: RenderEditorLocalState = { ...defaultEditorState, status };
    const view = buildPresentation("render.viewer", "渲染查看器", state);
    assert.ok(view.message.length > 0);
    assert.ok(view.stateLabel.length > 0);
  }
  const offline = buildPresentation("render.viewer", "渲染查看器", {
    ...defaultEditorState,
    status: "offline",
    executionMode: "blocked",
  });
  assert.equal(offline.actions[0].commandId, "integration.open");
  assert.match(offline.message, /不会.*实时/);
});

test("ready editors expose their production-specific review surface", () => {
  const expected = new Map([
    ["render.viewer", "Depth · Normal · Object ID"],
    ["render.aov-viewer", "Beauty · Depth · Normal · Albedo · Object ID"],
    ["render.recipe", "Lighting/Visibility · Fixed Camera"],
    ["render.queue", "取消 · 重试 · 持久化"],
    ["render.comparison", "几何与相机版本不变"],
    ["render.provenance", "Workflow · Model · Seed · Prompt"],
  ]);
  for (const editorId of expected.keys()) {
    const view = buildPresentation(editorId, editorId, {
      ...defaultEditorState,
      status: "ready",
      executionMode: "mock",
      selectedId: "fixture-selection",
    });
    const values = view.sections.flatMap((section) => section.rows.map((row) => row.value));
    assert.ok(values.includes(expected.get(editorId) as string), editorId);
  }
});

test("hidden queue keeps serializable selection while polling is suspended", () => {
  const hidden: RenderEditorLocalState = {
    ...defaultEditorState,
    status: "ready",
    executionMode: "live",
    selectedId: "rjob_42",
    filter: "running",
    visible: false,
  };
  const locallyRestored = restoreEditorState(serializeEditorState(hidden));
  assert.equal(locallyRestored.executionMode, "planned");
  const restored = applyServerEditorState(locallyRestored, {
    status: "ready",
    executionMode: "live",
    selectedId: "rjob_42",
    errorCode: null,
  });
  assert.equal(restored.selectedId, "rjob_42");
  assert.equal(restored.filter, "running");
  assert.equal(restored.visible, false);
  const view = buildPresentation("render.queue", "渲染队列", restored);
  assert.equal(view.preservesServerQueue, true);
  assert.match(view.message, /队列.*持久化.*轮询.*暂停/);
});

test("execution mode and status are restored only from server state", () => {
  const serialized = serializeEditorState({
    ...defaultEditorState,
    status: "ready",
    executionMode: "live",
  }) as Record<string, unknown>;
  assert.equal("executionMode" in serialized, false);
  assert.equal("status" in serialized, false);
  const restored = restoreEditorState({
    ...serialized,
    executionMode: "live",
    status: "ready",
  });
  assert.equal(restored.executionMode, "planned");
  assert.equal(restored.status, "empty");
  const planned = buildPresentation("render.viewer", "渲染查看器", {
    ...restored,
    status: "ready",
  });
  assert.equal(planned.tone, "info");
  assert.match(planned.message, /尚未生成/);
});

test("pinned context restores without storing server entities", () => {
  const restored = restoreEditorState({
    ...defaultEditorState,
    contextBinding: {
      mode: "pinned",
      context: {
        projectId: "prj_home",
        sceneId: "scn_hall",
        activeRenderJobId: "rjob_1",
        serverEntity: { shouldNotPersist: true },
      },
    },
  });
  assert.deepEqual(restored.contextBinding, {
    mode: "pinned",
    context: { projectId: "prj_home", sceneId: "scn_hall", activeRenderJobId: "rjob_1" },
  });
  assert.equal("job" in (serializeEditorState(restored) as Record<string, unknown>), false);
});

test("feature editors never call external integrations or shell internals directly", async () => {
  const files = [
    "RenderViewerEditor.tsx",
    "AovViewerEditor.tsx",
    "RecipeEditor.tsx",
    "QueueEditor.tsx",
    "ComparisonEditor.tsx",
    "ProvenanceEditor.tsx",
    "EditorFrame.tsx",
  ];
  for (const file of files) {
    const source = await readFile(new URL(`../editors/${file}`, import.meta.url), "utf8");
    assert.doesNotMatch(source, /\bfetch\s*\(/);
    assert.doesNotMatch(source, /dockview|ComfyUIAdapter|Blender|UnityEngine/);
  }
});

test("frontend manifest mirrors the module manifest identifiers", async () => {
  const yaml = await readFile(new URL("../../../module.yaml", import.meta.url), "utf8");
  assert.match(yaml, /\nid: render-ops\n/);
  for (const id of expectedEditors) assert.match(yaml, new RegExp(`- ${id.replace(".", "\\.")}`));
});
