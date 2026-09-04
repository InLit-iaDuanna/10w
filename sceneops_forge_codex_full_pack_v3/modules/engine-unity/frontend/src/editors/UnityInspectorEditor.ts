import { integrationState } from "../editor-state.ts";
import type { ExecutionMode, UnityEditorState } from "../types.ts";

export interface UnityInspectorViewInput {
  mode: ExecutionMode;
  moduleEnabled: boolean;
  permitted: boolean;
  connected: boolean;
  selectedSceneOpsId: string | null;
}
export default function createUnityInspectorView(
  input: UnityInspectorViewInput,
): UnityEditorState {
  return integrationState(input.mode, {
    enabled: input.moduleEnabled,
    permitted: input.permitted,
    connected: input.connected,
    hasSelection: Boolean(input.selectedSceneOpsId),
  });
}
