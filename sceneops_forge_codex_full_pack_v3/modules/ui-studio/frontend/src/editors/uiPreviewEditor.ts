export const uiPreviewEditor = {
  id: "ui.preview", title: "UI 预览", icon: "monitor", category: "logic",
  defaultPlacement: "right", minWidth: 360, minHeight: 240, singleton: false,
  requiredPermissions: ["ui:read"], optionalIntegrations: ["unity"],
  load: () => import("./uiPreviewEditorView"),
};
