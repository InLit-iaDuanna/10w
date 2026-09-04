import { logicCommandDefinitions } from "./commands/definitions.ts";
import { logicEditorDefinitions } from "./editors/definitions.ts";
import { logicStudioManifest } from "./manifest.ts";

export const moduleContribution = {
  manifest: logicStudioManifest,
  editors: logicEditorDefinitions,
  commands: logicCommandDefinitions,
  navigation: logicEditorDefinitions.map((editor) => ({
    editorId: editor.id,
    group: "逻辑与内容",
    keywords: ["logic", "graph", editor.title],
    recommendedEdges: editor.defaultPlacement === "bottom" ? ["bottom"] : ["right"],
  })),
};

export function resolveLogicStudioContribution(enabled: boolean) {
  return enabled ? moduleContribution : null;
}

export { createOpenLogicEditorAction } from "./commands/openLogicEditor.ts";
export { logicCommandDefinitions } from "./commands/definitions.ts";
export { logicEditorDefinitions } from "./editors/definitions.ts";
export {
  createLogicEditorState,
  restoreLogicEditorState,
  serializeLogicEditorState,
} from "./editors/state.ts";
export type {
  ContextBinding,
  ExecutionMode,
  LogicEditorDefinition,
  LogicEditorId,
  LogicEditorState,
  LogicEditorStatus,
  LogicEditorView,
} from "./editors/editorTypes.ts";
