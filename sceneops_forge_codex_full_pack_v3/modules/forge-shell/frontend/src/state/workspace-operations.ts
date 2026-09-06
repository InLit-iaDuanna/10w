import type {
  CommandSource,
  EditorAvailability,
  EditorInstance,
  EditorPlacement,
} from '../contracts.ts';

export interface OpenEditorRequest {
  editorId: string;
  placement?: EditorPlacement;
  source: CommandSource;
  confirmed?: boolean;
  forceReplaceDirty?: boolean;
  executionMode?: EditorInstance['executionMode'];
  preserveFocus?: boolean;
}

export type OpenEditorResult =
  | { status: 'opened'; instance: EditorInstance }
  | { status: 'focused'; instance: EditorInstance }
  | { status: 'confirmation-required'; reason: 'assistant-layout-change' | 'unsaved-editor' }
  | { status: 'rejected'; reason: 'locked-editor' | 'unknown-editor' | 'invalid-docking-mutation' }
  | { status: 'unavailable'; availability?: EditorAvailability; code?: 'POPOUT_BLOCKED' };

export type CloseEditorResult =
  | { status: 'closed'; instance: EditorInstance }
  | { status: 'confirmation-required'; reason: 'assistant-layout-change' | 'unsaved-editor' }
  | { status: 'rejected'; reason: 'locked-editor' | 'unknown-editor' };

export interface LayoutMutationAuthorization {
  source: CommandSource;
  confirmed?: boolean;
}

export type LayoutMutationResult =
  | { status: 'completed' }
  | { status: 'confirmation-required'; reason: 'assistant-layout-change' | 'unsaved-editor' }
  | { status: 'rejected'; reason: 'locked-editor' | 'unknown-editor' | 'invalid-docking-mutation' };
