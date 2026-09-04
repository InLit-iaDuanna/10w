import { integrationState } from "../editor-state.ts";
import type { ExecutionMode, UnityEditorState } from "../types.ts";

export default function createUnityBuildView(input: {
  mode: ExecutionMode;
  connected: boolean;
  failure?: { code: string; message: string; retryable: boolean };
}): UnityEditorState {
  return integrationState(input.mode, {
    enabled: true,
    permitted: true,
    connected: input.connected,
    hasSelection: true,
    failure: input.failure,
  });
}
