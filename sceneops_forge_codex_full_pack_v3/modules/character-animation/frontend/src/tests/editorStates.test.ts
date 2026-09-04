import { describe, expect, it } from 'vitest';
import {
  restoreAnimatorGraphState,
  restoreCharacterState,
  restoreRetargetState,
  restoreRigState,
  restoreTimelineState,
  serializeEditorState,
} from '../editorStates';

describe('serializable editor-local state', () => {
  it('round trips timeline and pinned selections without server entities', () => {
    const state = { selectedClipVersionId: 'clip_walk_v1', timeSeconds: 0.5, zoom: 1.25 };
    expect(restoreTimelineState(serializeEditorState(state))).toEqual(state);
    expect(restoreRigState({ selectedBoneId: 'bone_head', showHierarchyIds: false })).toEqual({
      selectedBoneId: 'bone_head',
      showHierarchyIds: false,
    });
  });

  it('restores bounded defaults from invalid persisted values', () => {
    expect(restoreCharacterState({ selectedPanel: 'unknown' }).selectedPanel).toBe('overview');
    expect(restoreTimelineState({ timeSeconds: Number.NaN, zoom: 'large' })).toEqual({
      selectedClipVersionId: null,
      timeSeconds: 0,
      zoom: 1,
    });
    expect(restoreRetargetState(null).synchronizeCamera).toBe(true);
    expect(restoreAnimatorGraphState(undefined).selectedStateId).toBeNull();
  });
});
