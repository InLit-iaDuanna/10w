import { conceptCommands, conceptOpenCommand } from "./commands/definitions.ts";
import { conceptEditors, manifest } from "./manifest.ts";

export const moduleContribution = {
  manifest,
  editors: conceptEditors,
  commands: [conceptOpenCommand, ...conceptCommands.slice(1)],
  navigation: [
    {
      editorId: "concept.moodboard",
      group: "概念与资产",
      keywords: ["概念", "情绪板", "moodboard", "任务"],
      recommendedEdges: ["left", "right"],
    },
    {
      editorId: "concept.style_bible",
      group: "概念与资产",
      keywords: ["风格", "style bible", "project bible"],
      recommendedEdges: ["right"],
    },
  ],
} as const;

export { openConcept } from "./commands/openConcept.ts";
export {
  defaultConceptEditorState,
  generationOfflineAvailability,
  resolveEditorAvailability,
  restoreConceptEditorState,
  serializeConceptEditorState,
} from "./editors/presentation.ts";
export type {
  ConceptEditorLocalState,
  EditorAvailability,
  MoodboardPresentation,
  StyleBiblePresentation,
} from "./types.ts";
