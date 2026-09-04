import {
  defaultConceptEditorState,
  restoreConceptEditorState,
  serializeConceptEditorState,
} from "./editors/presentation.ts";

export const manifest = {
  schemaVersion: 1,
  id: "concept-lab",
  version: "0.1.0",
  featureFlag: "concept_lab",
} as const;

export const conceptEditors = [
  {
    id: "concept.moodboard",
    title: "概念情绪板",
    icon: "images",
    category: "concept",
    load: () => import("./editors/MoodboardEditor.tsx"),
    defaultPlacement: "right",
    minWidth: 420,
    minHeight: 300,
    singleton: false,
    requiredPermissions: ["concept:read"],
    optionalIntegrations: ["image-generation", "artifact-store"],
    supportsContextBinding: true,
    defaultState: defaultConceptEditorState,
    serializeState: serializeConceptEditorState,
    restoreState: restoreConceptEditorState,
  },
  {
    id: "concept.style_bible",
    title: "风格圣经",
    icon: "book-open",
    category: "concept",
    load: () => import("./editors/StyleBibleEditor.tsx"),
    defaultPlacement: "right",
    minWidth: 360,
    minHeight: 280,
    singleton: false,
    requiredPermissions: ["concept:read"],
    optionalIntegrations: [],
    supportsContextBinding: true,
    defaultState: defaultConceptEditorState,
    serializeState: serializeConceptEditorState,
    restoreState: restoreConceptEditorState,
  },
] as const;
