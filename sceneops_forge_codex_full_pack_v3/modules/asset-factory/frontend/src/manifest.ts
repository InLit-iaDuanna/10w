export const manifest = {
  schemaVersion: 1,
  id: "asset-factory",
  version: "0.1.0",
  featureFlag: "asset_factory",
} as const;

const editorBase = {
  category: "asset",
  minWidth: 380,
  minHeight: 300,
  singleton: false,
  requiredPermissions: ["asset:read", "asset:write"],
  requiredIntegrations: ["blender"],
  contextBinding: true,
} as const;

export const assetFactoryEditor = {
  ...editorBase,
  id: "asset.factory",
  title: "资产工厂",
  icon: "factory",
  defaultPlacement: "center",
  load: () => import("./editors/AssetFactoryEditor.ts"),
} as const;

export const assetValidationEditor = {
  ...editorBase,
  id: "asset.validation",
  title: "资产质量检查",
  icon: "check-circle",
  defaultPlacement: "right",
  load: () => import("./editors/AssetValidationEditor.ts"),
} as const;

export const moduleContribution = {
  manifest,
  editors: [assetFactoryEditor, assetValidationEditor],
  commands: [
    ["asset.pipeline.preview", "预演资产流水线", ["asset:write"]],
    ["asset.pipeline.run", "运行资产流水线", ["asset:write"]],
    ["asset.pipeline.cancel", "取消资产流水线", ["asset:write"]],
    ["asset.pipeline.retry", "重试资产流水线", ["asset:write"]],
    ["asset.pipeline.rollback", "回滚 Blender 快照", ["asset:write"]],
    ["asset.pipeline.publish", "发布资产版本", ["asset:publish"]],
  ].map(([id, title, requiredPermissions]) => ({
    id,
    title,
    requiredPermissions,
    requiredIntegrations: ["blender"],
    inputContract: id === "asset.pipeline.publish" ? "PublicationRequest" : "PipelineRequest",
  })),
  navigation: [
    {
      editorId: "asset.factory",
      group: "资产",
      keywords: ["Blender", "资产工厂", "GLB", "FBX"],
      recommendedEdges: ["left", "bottom"],
    },
    {
      editorId: "asset.validation",
      group: "资产",
      keywords: ["质量", "gate", "triangles", "UV"],
      recommendedEdges: ["right"],
    },
  ],
} as const;
