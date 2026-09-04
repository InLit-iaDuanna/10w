import { commandDefinitions } from "./commands/definitions.ts";
import type { ModuleContribution } from "./contracts.ts";
import { editorDefinitions, navigationEntries, reviewWorkspace } from "./editors/definitions.ts";
import { manifest } from "./manifest.ts";

export const moduleContribution: ModuleContribution = {
  manifest,
  editors: editorDefinitions,
  commands: commandDefinitions,
  workspacePresets: [reviewWorkspace],
  navigation: navigationEntries,
};

export { reviewKeys } from "./hooks/queryKeys.ts";
export { VersionReviewWorkbench } from "./lab/VersionReviewWorkbench.tsx";
export {
  defaultReviewEditorState,
  restoreReviewEditorState,
  serializeReviewEditorState,
} from "./state/reviewEditorState.ts";
export type { VersionCollaborationApi } from "./api.ts";
export type { ReviewContextBinding, ReviewEditorState, ReviewLayer } from "./state/reviewEditorState.ts";
