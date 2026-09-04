import assert from "node:assert/strict";
import test from "node:test";

import {
  buildAssetEditorState,
  emptyAssetFilter,
  filterAssets,
  moduleContribution,
  type AssetSummary,
} from "../index.ts";

const keyAsset: AssetSummary = {
  assetId: "ast_key",
  assetVersionId: "aver_key_1",
  assetVersionNumber: 1,
  displayName: "归家钥匙",
  category: "prop",
  sourcePath: "Assets/Props/key.blend",
  sourceKind: "imported",
  sourceVersion: "1",
  formats: ["glb", "fbx"],
  dimensionsM: { x: 0.04, y: 0.01, z: 0.1 },
  triangleCount: 840,
  materialCount: 1,
  textureCount: 2,
  hasUv: true,
  isRigged: false,
  animationNames: [],
  lodCount: 2,
  colliderKind: "convex_hull",
  licenseName: "CC0-1.0",
  hasAiProvenance: false,
  aiProvenanceProviders: [],
  sceneIds: ["scn_home_hallway"],
  unityStatus: "imported",
  buildIds: ["bld_home_7"],
  gateStatuses: ["passed"],
  executionMode: "mock",
};

const obstacle: AssetSummary = {
  ...keyAsset,
  assetId: "ast_obstacle",
  assetVersionId: "aver_obstacle_1",
  displayName: "仓库路障",
  sourcePath: "Assets/Props/warehouse-obstacle.blend",
  triangleCount: 2200,
  lodCount: 0,
  sceneIds: ["scn_warehouse"],
  unityStatus: "unavailable",
  buildIds: [],
};

test("public contribution registers lazy browser and inspector", () => {
  assert.equal(moduleContribution.manifest.id, "asset-library");
  assert.deepEqual(
    moduleContribution.editors.map((editor) => editor.id),
    ["asset.browser", "asset.inspector"],
  );
  assert.equal(moduleContribution.editors[0].requiredPermissions[0], "asset:read");
});

test("filters source, geometry, LOD, collider, Unity, scene, and build text", () => {
  const result = filterAssets([obstacle, keyAsset], {
    ...emptyAssetFilter,
    query: "home_7",
    formats: ["GLB", "fbx"],
    hasUv: true,
    hasLod: true,
    hasCollider: true,
    unityStatus: "imported",
    maxTriangles: 1000,
    executionModes: ["mock"],
  });
  assert.deepEqual(result.map((asset) => asset.assetId), ["ast_key"]);
});

test("shows permission, disconnected, loading, failed, empty, and mode-labelled success", () => {
  const base = { loading: false, permissionGranted: true, connected: true, assets: [keyAsset] };
  assert.equal(buildAssetEditorState({ ...base, permissionGranted: false }, emptyAssetFilter).kind, "permission");
  assert.equal(buildAssetEditorState({ ...base, connected: false }, emptyAssetFilter).kind, "disconnected");
  assert.equal(buildAssetEditorState({ ...base, loading: true }, emptyAssetFilter).kind, "loading");
  assert.equal(
    buildAssetEditorState({ ...base, error: { code: "FAILED", message: "读取失败" } }, emptyAssetFilter).kind,
    "failed",
  );
  assert.equal(buildAssetEditorState({ ...base, assets: [] }, emptyAssetFilter).kind, "empty");
  const ready = buildAssetEditorState(base, emptyAssetFilter);
  assert.equal(ready.kind, "ready");
  if (ready.kind === "ready") assert.deepEqual(ready.modeLabels, ["mock"]);
});
