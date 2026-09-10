export interface LocalEditorDefinition {
  id: string;
  title: string;
  icon: string;
  category: string;
  load: () => Promise<{ default: unknown }>;
  defaultPlacement: "left" | "right";
  minWidth: number;
  minHeight: number;
  singleton: boolean;
  requiredPermissions: string[];
  optionalIntegrations: string[];
  contextBinding: true;
}

export const manifest = {
  schemaVersion: 1,
  id: "asset-library",
  version: "0.1.0",
  featureFlag: "asset_library",
} as const;

export const assetBrowserEditor: LocalEditorDefinition = {
  id: "asset.browser",
  title: "资产浏览器",
  icon: "archive",
  category: "asset",
  load: () => import("./editors/AssetBrowserEditor.ts"),
  defaultPlacement: "left",
  minWidth: 320,
  minHeight: 260,
  singleton: false,
  requiredPermissions: ["asset:read"],
  optionalIntegrations: ["unity"],
  contextBinding: true,
};

export const assetInspectorEditor: LocalEditorDefinition = {
  id: "asset.inspector",
  title: "资产检查器",
  icon: "inspect",
  category: "asset",
  load: () => import("./editors/AssetInspectorEditor.ts"),
  defaultPlacement: "right",
  minWidth: 300,
  minHeight: 280,
  singleton: false,
  requiredPermissions: ["asset:read"],
  optionalIntegrations: ["unity"],
  contextBinding: true,
};

export const moduleContribution = {
  manifest,
  editors: [assetBrowserEditor, assetInspectorEditor,
    {id:'asset.builtin-library',title:'内置场景与资产',category:'asset',requiredPermissions:['asset:read']}],
  commands: [
    {
      id: "asset.search",
      title: "搜索资产",
      requiredPermissions: ["asset:read"],
      inputContract: "AssetSearchFilter",
    },
    {
      id: "asset.version.publish",
      title: "发布资产版本",
      requiredPermissions: ["asset:publish"],
      inputContract: "PublicationRequest",
    },
  ],
  navigation: [
    {
      editorId: "asset.browser",
      group: "资产",
      keywords: ["资产", "模型", "asset", "GLB", "FBX"],
      recommendedEdges: ["left"],
    },
    {
      editorId: "asset.inspector",
      group: "资产",
      keywords: ["检查", "来源", "版本", "Unity"],
      recommendedEdges: ["right"],
    },
  ],
} as const;
