export interface ProjectIntakeManifest {
  readonly schema_version: 1;
  readonly id: "project-intake";
  readonly version: string;
  readonly title: string;
  readonly description: string;
  readonly status: "active";
  readonly feature_flag: "project_intake";
  readonly requires: {
    readonly modules: readonly string[];
    readonly integrations: readonly string[];
    readonly optional_integrations: readonly string[];
  };
  readonly contributes: {
    readonly editors: readonly string[];
    readonly commands: readonly string[];
    readonly events: readonly string[];
    readonly jobs: readonly string[];
    readonly workflows: readonly string[];
    readonly policy_gates: readonly string[];
  };
  readonly permissions: readonly string[];
  readonly entrypoints: { readonly frontend: string };
}

export const moduleManifest: ProjectIntakeManifest = {
  schema_version: 1,
  id: "project-intake",
  version: "0.1.0",
  title: "Project Intake",
  description: "Turns a new-project brief or an existing-project scan into confirmed production intent.",
  status: "active",
  feature_flag: "project_intake",
  requires: {
    modules: ["core-kernel", "module-runtime"],
    integrations: [],
    optional_integrations: ["unity", "blender"],
  },
  contributes: {
    editors: ["project.intake"],
    commands: [
      "project.intake.create_new_draft",
      "project.intake.draft_from_conversation",
      "project.intake.scan_existing",
      "project.intake.confirm_field",
    ],
    events: ["project.intake.drafted@1", "project.intake.field_confirmed@1"],
    jobs: [],
    workflows: [],
    policy_gates: [],
  },
  permissions: ["project:read", "project:write", "project:scan"],
  entrypoints: { frontend: "./frontend/src/index.ts" },
};

export const projectIntakeEditorDefinition = {
  id: "project.intake",
  title: "项目入口",
  icon: "folder-search",
  category: "project",
  load: () => import("./editors/ProjectIntakeEditor.ts"),
  defaultPlacement: "center",
  minWidth: 420,
  minHeight: 300,
  singleton: true,
  requiredPermissions: ["project:read"],
  optionalIntegrations: ["unity", "blender"],
  supportedStates: [
    "loading",
    "empty",
    "ready",
    "failed",
    "integration-offline",
    "permission-denied",
    "module-disabled",
  ],
} as const;

export const projectIntakeCommandDefinitions = moduleManifest.contributes.commands.map((id) => ({
  id,
  moduleId: moduleManifest.id,
}));

export const moduleContribution = {
  manifest: moduleManifest,
  editors: [projectIntakeEditorDefinition],
  commands: projectIntakeCommandDefinitions,
  navigation: [
    {
      editorId: "project.intake",
      group: "项目",
      keywords: ["项目", "导入", "扫描", "intake"],
      recommendedEdges: ["left"],
    },
  ],
} as const;
