export interface CharacterEditorState {
  selectedPanel: 'overview' | 'versions' | 'unity';
}

export interface RigInspectorState {
  selectedBoneId: string | null;
  showHierarchyIds: boolean;
}

export interface SkinQaState {
  selectedCheckCode: string | null;
}

export interface AnimationTimelineState {
  selectedClipVersionId: string | null;
  timeSeconds: number;
  zoom: number;
}

export interface RetargetPreviewState {
  selectedProfileId: string | null;
  synchronizeCamera: boolean;
}

export interface AnimatorGraphState {
  selectedStateId: string | null;
  zoom: number;
}

export const defaultCharacterState: CharacterEditorState = { selectedPanel: 'overview' };
export const defaultRigState: RigInspectorState = { selectedBoneId: null, showHierarchyIds: true };
export const defaultSkinQaState: SkinQaState = { selectedCheckCode: null };
export const defaultTimelineState: AnimationTimelineState = { selectedClipVersionId: null, timeSeconds: 0, zoom: 1 };
export const defaultRetargetState: RetargetPreviewState = { selectedProfileId: null, synchronizeCamera: true };
export const defaultAnimatorGraphState: AnimatorGraphState = { selectedStateId: null, zoom: 1 };

export function restoreCharacterState(value: unknown): CharacterEditorState {
  const panel = record(value).selectedPanel;
  return { selectedPanel: panel === 'versions' || panel === 'unity' ? panel : 'overview' };
}

export function restoreRigState(value: unknown): RigInspectorState {
  const source = record(value);
  return {
    selectedBoneId: typeof source.selectedBoneId === 'string' ? source.selectedBoneId : null,
    showHierarchyIds: source.showHierarchyIds !== false,
  };
}

export function restoreSkinQaState(value: unknown): SkinQaState {
  const selected = record(value).selectedCheckCode;
  return { selectedCheckCode: typeof selected === 'string' ? selected : null };
}

export function restoreTimelineState(value: unknown): AnimationTimelineState {
  const source = record(value);
  return {
    selectedClipVersionId: typeof source.selectedClipVersionId === 'string' ? source.selectedClipVersionId : null,
    timeSeconds: finiteNumber(source.timeSeconds, 0),
    zoom: finiteNumber(source.zoom, 1),
  };
}

export function restoreRetargetState(value: unknown): RetargetPreviewState {
  const source = record(value);
  return {
    selectedProfileId: typeof source.selectedProfileId === 'string' ? source.selectedProfileId : null,
    synchronizeCamera: source.synchronizeCamera !== false,
  };
}

export function restoreAnimatorGraphState(value: unknown): AnimatorGraphState {
  const source = record(value);
  return {
    selectedStateId: typeof source.selectedStateId === 'string' ? source.selectedStateId : null,
    zoom: finiteNumber(source.zoom, 1),
  };
}

export function serializeEditorState<TState>(state: TState): TState {
  return structuredClone(state);
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : {};
}

function finiteNumber(value: unknown, defaultValue: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : defaultValue;
}
