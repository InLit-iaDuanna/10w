export const logicStudioManifest = {
  schemaVersion: 1,
  id: "logic-studio",
  version: "0.1.0",
  featureFlag: "logic_studio",
  optionalIntegrations: ["unity"],
  permissions: [
    "logic:read",
    "logic:write",
    "logic:test",
    "logic:code:review",
    "logic:code:approve",
  ],
};
