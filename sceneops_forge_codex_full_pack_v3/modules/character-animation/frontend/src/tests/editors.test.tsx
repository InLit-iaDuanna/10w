import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import EditorStateFrame from '../components/EditorStateFrame';
import CharacterEditor from '../editors/CharacterEditor';
import RigInspectorEditor from '../editors/RigInspectorEditor';
import { defaultCharacterState, defaultRigState } from '../editorStates';
import { rememberHomeCharacterBundle } from '../fixtures/rememberHome';

const commonProps = {
  instanceId: 'editor_test',
  contextBinding: { mode: 'pinned' as const, context: { activeFeatureId: 'feature_key_door_branch' } },
  invokeCommand: vi.fn(),
};

describe('character animation editor states', () => {
  it('shows imported identity, feature links, and truthful mode in Character Editor', () => {
    render(
      <CharacterEditor
        {...commonProps}
        localState={defaultCharacterState}
        updateLocalState={vi.fn()}
        runtime={{ kind: 'ready', mode: 'mock', data: { bundle: rememberHomeCharacterBundle } }}
      />,
    );
    expect(screen.getByText('归家者')).toBeInTheDocument();
    expect(screen.getByText('feature_key_door_branch')).toBeInTheDocument();
    expect(screen.getByLabelText('执行模式：MOCK')).toBeInTheDocument();
    expect(screen.getByText('导入')).toBeInTheDocument();
  });

  it('renders loading, empty, failure, offline, and permission states visibly', () => {
    const states = [
      { kind: 'loading' as const, mode: 'planned' as const, message: '加载中' },
      { kind: 'empty' as const, mode: 'planned' as const, message: '没有角色' },
      { kind: 'failure' as const, mode: 'blocked' as const, message: '检查失败' },
      { kind: 'offline' as const, mode: 'blocked' as const, message: 'Unity 离线' },
      { kind: 'permission' as const, mode: 'blocked' as const, message: '没有权限' },
    ];
    for (const state of states) {
      const { unmount } = render(<EditorStateFrame title="测试编辑器" state={state}>{() => null}</EditorStateFrame>);
      expect(screen.getByText(state.message)).toBeInTheDocument();
      unmount();
    }
  });

  it('offers an actual retry action for recoverable failure', () => {
    const retry = vi.fn();
    render(
      <EditorStateFrame title="预览" state={{ kind: 'offline', mode: 'blocked', message: '集成离线', retry }}>
        {() => null}
      </EditorStateFrame>,
    );
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it('updates only local selection when a rig bone is selected', () => {
    const updateLocalState = vi.fn();
    render(
      <RigInspectorEditor
        {...commonProps}
        localState={defaultRigState}
        updateLocalState={updateLocalState}
        runtime={{ kind: 'ready', mode: 'cached', data: { rig: rememberHomeCharacterBundle.rig } }}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Head' }));
    expect(updateLocalState).toHaveBeenCalledWith({ selectedBoneId: 'bone_head' });
    expect(screen.getByLabelText('执行模式：CACHED')).toBeInTheDocument();
  });
});
