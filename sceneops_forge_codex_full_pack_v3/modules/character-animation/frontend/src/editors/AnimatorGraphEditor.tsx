import type { AnimatorStateSpec } from '../api-types';
import EditorStateFrame from '../components/EditorStateFrame';
import type { AnimatorGraphState } from '../editorStates';
import type { EditorProps } from '../types';

export interface AnimatorGraphData {
  states: AnimatorStateSpec[];
}

export default function AnimatorGraphEditor({ runtime, localState, updateLocalState }: EditorProps<AnimatorGraphState, AnimatorGraphData>) {
  return (
    <EditorStateFrame title="Animator 状态图" state={runtime}>
      {({ states }) => (
        <>
          <p>缩放：{localState.zoom.toFixed(1)}× · 选择：{localState.selectedStateId ?? '无'}</p>
          <ul className="character-animation-list" aria-label="Animator 状态">
            {states.map((state) => (
              <li key={state.animator_state_id}>
                <button onClick={() => updateLocalState({ selectedStateId: state.animator_state_id })}>{state.name}</button>
                <span>{state.clip_version_id} · {state.transitions?.length ?? 0} 个转换</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </EditorStateFrame>
  );
}
