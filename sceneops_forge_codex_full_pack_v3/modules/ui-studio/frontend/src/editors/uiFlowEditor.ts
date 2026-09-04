export const uiFlowEditor = {
  id: "ui.flow", title: "UI 流程", icon: "workflow", category: "logic",
  defaultPlacement: "center", minWidth: 420, minHeight: 280, singleton: false,
  requiredPermissions: ["ui:read"], optionalIntegrations: ["unity"],
  load: () => import("./uiFlowEditorView"),
};
