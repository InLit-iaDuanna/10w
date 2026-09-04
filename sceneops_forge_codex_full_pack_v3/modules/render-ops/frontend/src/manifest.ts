import type { EditorDefinition } from "./contracts.ts";
import { restoreEditorState, serializeEditorState } from "./state.ts";

function editor(
  id: string,
  title: string,
  icon: string,
  placement: "center" | "bottom" | "right",
  loader: () => Promise<unknown>,
): EditorDefinition {
  return {
    id,
    title,
    icon,
    category: "render",
    load: loader,
    defaultPlacement: placement,
    minWidth: placement === "right" ? 320 : 420,
    minHeight: placement === "bottom" ? 220 : 280,
    singleton: false,
    requiredPermissions: ["render:read"],
    optionalIntegrations: ["comfyui", "blender", "unity"],
    serializeState: serializeEditorState,
    restoreState: restoreEditorState,
  };
}

export const renderEditors: EditorDefinition[] = [
  editor("render.viewer", "渲染查看器", "image", "center", () => import("./editors/RenderViewerEditor.tsx")),
  editor("render.aov-viewer", "AOV 查看器", "layers", "center", () => import("./editors/AovViewerEditor.tsx")),
  editor("render.recipe", "渲染配方", "sliders", "right", () => import("./editors/RecipeEditor.tsx")),
  editor("render.queue", "渲染队列", "list", "bottom", () => import("./editors/QueueEditor.tsx")),
  editor("render.comparison", "渲染对比", "compare", "center", () => import("./editors/ComparisonEditor.tsx")),
  editor("render.provenance", "渲染来源", "history", "right", () => import("./editors/ProvenanceEditor.tsx")),
];

export const commandIds = [
  "render.brief.create",
  "render.aov.capture",
  "render.recipe.run",
  "render.job.cancel",
  "render.job.retry",
  "render.variant.approve",
  "render.writeback.propose",
  "render.writeback.apply",
  "render.validation.run",
] as const;

export const eventIds = [
  "render.job.started@1",
  "render.job.progressed@1",
  "render.job.failed@1",
  "render.job.cancelled@1",
  "render.variant.created@1",
  "render.writeback.proposed@1",
  "render.validation.completed@1",
] as const;

export const moduleContribution = {
  manifest: {
    id: "render-ops",
    version: "0.1.0",
    featureFlag: "render_ops",
    source: "../../module.yaml",
  },
  editors: renderEditors,
  commands: commandIds,
  events: eventIds,
  navigation: renderEditors.map((definition) => ({
    editorId: definition.id,
    group: "渲染",
    keywords: ["render", "AOV", "渲染", definition.title],
    recommendedEdges: definition.defaultPlacement === "bottom" ? ["bottom"] : ["right"],
  })),
  workspacePresets: [
    {
      id: "render",
      title: "渲染",
      requiresConfirmation: true,
      areas: ["render.aov-viewer", "render.viewer", "render.recipe", "render.queue"],
    },
  ],
  isEnabled(flags: Readonly<Record<string, boolean>>): boolean {
    return flags.render_ops === true;
  },
};

export const renderKeys = {
  all: ["render-ops"] as const,
  jobs: (projectId: string) => ["render-ops", "jobs", projectId] as const,
  job: (jobId: string) => ["render-ops", "job", jobId] as const,
  manifest: (manifestId: string) => ["render-ops", "manifest", manifestId] as const,
};
