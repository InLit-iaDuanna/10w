import type { EditorSnapshot } from "../state/editor-state.ts";

export interface BuildReleaseEditorComponentProps {
  snapshot?: EditorSnapshot;
  onCommand?: (commandId: string) => void;
}
