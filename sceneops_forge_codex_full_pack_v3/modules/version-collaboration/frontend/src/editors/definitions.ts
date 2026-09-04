import type { EditorDefinition, ToolLibraryEntry, WorkspacePresetContribution } from "../contracts.ts";
import {
  restoreReviewEditorState,
  serializeReviewEditorState,
} from "../state/reviewEditorState.ts";

const serializeState = (value: unknown) =>
  serializeReviewEditorState(restoreReviewEditorState(value));

export const editorDefinitions: readonly EditorDefinition[] = [
  {
    id: "review.version-diff",
    title: "版本四层差异",
    icon: "diff",
    category: "review",
    load: () => import("./VersionDiffEditor.tsx"),
    defaultPlacement: "center",
    minWidth: 480,
    minHeight: 320,
    singleton: false,
    requiredPermissions: ["review:read"],
    requiredIntegrations: [],
    optionalIntegrations: ["git", "render-ops", "ai-playtest"],
    supportsContextBinding: true,
    serializeState,
    restoreState: restoreReviewEditorState,
  },
  {
    id: "review.session",
    title: "评审与审批",
    icon: "review",
    category: "review",
    load: () => import("./ReviewSessionEditor.tsx"),
    defaultPlacement: "right",
    minWidth: 360,
    minHeight: 280,
    singleton: false,
    requiredPermissions: ["review:read"],
    requiredIntegrations: [],
    optionalIntegrations: ["git-lfs", "build-release"],
    supportsContextBinding: true,
    serializeState,
    restoreState: restoreReviewEditorState,
  },
  {
    id: "review.activity",
    title: "协作活动",
    icon: "activity",
    category: "review",
    load: () => import("./ActivityEditor.tsx"),
    defaultPlacement: "bottom",
    minWidth: 420,
    minHeight: 180,
    singleton: false,
    requiredPermissions: ["review:read"],
    requiredIntegrations: [],
    optionalIntegrations: [],
    supportsContextBinding: true,
    serializeState,
    restoreState: restoreReviewEditorState,
  },
];

export const reviewWorkspace: WorkspacePresetContribution = {
  id: "review",
  title: "评审",
  activateOnFreshLaunch: false,
  areas: [
    { editorId: "review.version-diff", placement: "center" },
    { editorId: "review.session", placement: "right", relativeTo: "review.version-diff" },
    { editorId: "review.activity", placement: "bottom", relativeTo: "review.version-diff" },
  ],
};

export const navigationEntries: readonly ToolLibraryEntry[] = editorDefinitions.map((editor) => ({
  editorId: editor.id,
  group: "评审与版本",
  keywords: ["评审", "版本", "diff", "approval", "rollback"],
  recommendedEdges: editor.defaultPlacement === "bottom" ? ["bottom"] : ["right"],
}));
