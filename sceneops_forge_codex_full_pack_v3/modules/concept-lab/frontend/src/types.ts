export type ExecutionMode = "live" | "cached" | "mock" | "planned" | "blocked";
export type EditorAvailability =
  | { kind: "loading" }
  | { kind: "empty"; message: string }
  | { kind: "failed"; message: string; retryCommandId: string }
  | { kind: "offline"; message: string; importCommandId: string }
  | { kind: "permission"; message: string }
  | { kind: "disabled"; message: string }
  | { kind: "ready" };

export interface MoodboardItemPresentation {
  id: string;
  title: string;
  view: string;
  thumbnailUrl?: string;
  permissionStatus: "cleared" | "warning" | "blocked";
  executionMode: ExecutionMode;
  decision: "proposed" | "approved" | "rejected";
}

export interface MoodboardPresentation {
  availability: EditorAvailability;
  conceptId: string | null;
  subject: string | null;
  executionMode: ExecutionMode;
  items: MoodboardItemPresentation[];
  notice: string | null;
}

export interface StyleBiblePresentation {
  availability: EditorAvailability;
  projectBibleVersionId: string | null;
  conceptId: string | null;
  styleConstraints: string[];
  forbiddenElements: string[];
  latestAssessment: "consistent" | "needs_review" | "inconsistent" | null;
  confidence: number | null;
  evidenceCoverage: number | null;
  subjectiveNotice: string;
}

export interface ConceptEditorLocalState {
  selectedVariantIds: string[];
  showRejected: boolean;
  pinnedConceptId: string | null;
}

export interface ConceptCommandClient {
  execute<TResult = unknown>(commandId: string, input: unknown): Promise<TResult>;
}

export interface ConceptEditorProps<TPresentation> {
  presentation: TPresentation;
  localState: ConceptEditorLocalState;
  updateLocalState(patch: Partial<ConceptEditorLocalState>): void;
  commands: ConceptCommandClient;
}
