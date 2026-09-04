import type { VersionCollaborationApi } from "../api.ts";
import type { ReviewEditorState } from "../state/reviewEditorState.ts";

export interface WorkbenchCommandClient {
  execute(commandId: string, input: unknown): Promise<unknown>;
}

export interface ReviewEditorRuntimeProps {
  readonly instanceId: string;
  readonly reviewId: string | null;
  readonly api: VersionCollaborationApi;
  readonly commands: WorkbenchCommandClient;
  readonly permissions: ReadonlySet<string>;
  readonly gitConnected: boolean;
  readonly localState: ReviewEditorState;
  readonly updateLocalState: (patch: Partial<ReviewEditorState>) => void;
}

export function resolveReviewBinding(props: ReviewEditorRuntimeProps): {
  readonly reviewId: string | null;
  readonly reviewRevisionId: string | null;
} {
  const binding = props.localState.contextBinding;
  return binding.mode === "pinned"
    ? {
        reviewId: binding.reviewId,
        reviewRevisionId: binding.reviewRevisionId,
      }
    : { reviewId: props.reviewId, reviewRevisionId: null };
}

export function errorCode(error: unknown): string | null {
  if (typeof error !== "object" || error === null || !("code" in error)) return error ? "UNKNOWN" : null;
  return typeof error.code === "string" ? error.code : "UNKNOWN";
}
