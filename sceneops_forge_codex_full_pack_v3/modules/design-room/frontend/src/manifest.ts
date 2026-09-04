export const moduleManifest = {
  schema_version: 1,
  id: "design-room",
  version: "0.1.0",
  title: "Design Room",
  description: "Owns structured Project Bibles, GDDs, Feature Specs, decisions, and design history.",
  status: "active",
  feature_flag: "design_room",
  requires: {
    modules: ["core-kernel", "module-runtime", "project-intake"],
    integrations: [],
    optional_integrations: [],
  },
  contributes: {
    editors: ["project.bible", "design.gdd", "design.feature_spec"],
    commands: [
      "design.project_bible.save_version",
      "design.gdd.save",
      "design.feature_spec.draft_from_conversation",
      "design.feature_spec.save_version",
      "design.change.propose",
      "design.change.approve",
      "design.feature_spec.mark_ready",
      "design.decision.create",
      "design.decision.reject_alternative",
      "design.decision.accept_alternative",
    ],
    events: [
      "design.project_bible.versioned@1",
      "design.feature_spec.versioned@1",
      "design.feature_spec.marked_ready@1",
      "design.decision.recorded@1",
    ],
    jobs: [],
    workflows: [],
    policy_gates: ["design.ai_change_approval", "design.planning_readiness"],
  },
  permissions: ["design:read", "design:write", "design:approve"],
  entrypoints: { frontend: "./frontend/src/index.ts" },
} as const;

export const designRoomEditorDefinitions = [
  {
    id: "project.bible",
    title: "Project Bible",
    icon: "book-open",
    category: "project",
    load: () => import("./editors/ProjectBibleEditor.ts"),
    defaultPlacement: "center",
    minWidth: 460,
    minHeight: 320,
    singleton: true,
    requiredPermissions: ["design:read"],
  },
  {
    id: "design.gdd",
    title: "GDD",
    icon: "file-tree",
    category: "project",
    load: () => import("./editors/GddEditor.ts"),
    defaultPlacement: "center",
    minWidth: 480,
    minHeight: 320,
    singleton: true,
    requiredPermissions: ["design:read"],
  },
  {
    id: "design.feature_spec",
    title: "Feature Spec",
    icon: "list-checks",
    category: "project",
    load: () => import("./editors/FeatureSpecEditor.ts"),
    defaultPlacement: "center",
    minWidth: 520,
    minHeight: 360,
    singleton: false,
    requiredPermissions: ["design:read"],
  },
] as const;

export const designRoomCommandDefinitions = moduleManifest.contributes.commands.map((id) => ({
  id,
  moduleId: moduleManifest.id,
}));

export const moduleContribution = {
  manifest: moduleManifest,
  editors: designRoomEditorDefinitions,
  commands: designRoomCommandDefinitions,
  navigation: [
    { editorId: "project.bible", group: "项目", keywords: ["bible", "规则", "项目圣经"], recommendedEdges: ["left"] },
    { editorId: "design.gdd", group: "项目", keywords: ["gdd", "游戏设计"], recommendedEdges: ["left"] },
    { editorId: "design.feature_spec", group: "项目", keywords: ["feature", "功能规格", "验收"], recommendedEdges: ["right"] },
  ],
} as const;
