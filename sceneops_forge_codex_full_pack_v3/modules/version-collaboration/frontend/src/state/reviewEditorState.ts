import type { ExecutionMode } from "../generated/api-types.ts";

export type ReviewLayer = "file" | "semantic" | "visual" | "behavior";

export type ReviewContextBinding =
  | { readonly mode: "follow-global" }
  | {
      readonly mode: "pinned";
      readonly projectId: string;
      readonly reviewId: string;
      readonly reviewRevisionId: string;
    };

export interface ReviewEditorState {
  readonly schemaVersion: 1;
  readonly selectedLayer: ReviewLayer;
  readonly contextBinding: ReviewContextBinding;
  readonly expectedMode: ExecutionMode | null;
}

export const defaultReviewEditorState: ReviewEditorState = Object.freeze({
  schemaVersion: 1,
  selectedLayer: "file",
  contextBinding: { mode: "follow-global" },
  expectedMode: null,
});

export function serializeReviewEditorState(state: ReviewEditorState): unknown {
  return structuredClone(state);
}

export function restoreReviewEditorState(value: unknown): ReviewEditorState {
  if (!isRecord(value) || value.schemaVersion !== 1) {
    throw new Error("REVIEW_STATE_SCHEMA_UNSUPPORTED");
  }
  if (!isLayer(value.selectedLayer) || !isContextBinding(value.contextBinding)) {
    throw new Error("REVIEW_STATE_INVALID");
  }
  const expectedMode = value.expectedMode;
  if (expectedMode !== null && !isExecutionMode(expectedMode)) {
    throw new Error("REVIEW_STATE_INVALID");
  }
  return {
    schemaVersion: 1,
    selectedLayer: value.selectedLayer,
    contextBinding: value.contextBinding,
    expectedMode,
  };
}

function isContextBinding(value: unknown): value is ReviewContextBinding {
  if (!isRecord(value)) return false;
  if (value.mode === "follow-global") return true;
  return (
    value.mode === "pinned" &&
    typeof value.projectId === "string" &&
    typeof value.reviewId === "string" &&
    typeof value.reviewRevisionId === "string"
  );
}

function isLayer(value: unknown): value is ReviewLayer {
  return value === "file" || value === "semantic" || value === "visual" || value === "behavior";
}

function isExecutionMode(value: unknown): value is ExecutionMode {
  return value === "live" || value === "cached" || value === "mock" || value === "planned" || value === "blocked";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
