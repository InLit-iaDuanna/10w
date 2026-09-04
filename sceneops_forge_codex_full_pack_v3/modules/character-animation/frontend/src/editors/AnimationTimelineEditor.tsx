import type { AnimationClipSpec, QualityReport } from '../api-types';
import EditorStateFrame from '../components/EditorStateFrame';
import type { AnimationTimelineState } from '../editorStates';
import type { EditorProps } from '../types';

export interface AnimationTimelineData {
  clips: AnimationClipSpec[];
  report: QualityReport;
}

export default function AnimationTimelineEditor({ runtime, localState, updateLocalState }: EditorProps<AnimationTimelineState, AnimationTimelineData>) {
  return (
    <EditorStateFrame title="动画时间线" state={runtime}>
      {({ clips, report }) => (
        <>
          <p>时间：{localState.timeSeconds.toFixed(2)} 秒 · 缩放：{localState.zoom.toFixed(1)}×</p>
          <ul className="character-animation-list" aria-label="动画片段">
            {clips.map((clip) => (
              <li key={clip.clip_version_id}>
                <button onClick={() => updateLocalState({ selectedClipVersionId: clip.clip_version_id, timeSeconds: 0 })}>
                  {clip.name}
                </button>
                <span>{clip.duration_seconds.toFixed(2)}s · {clip.loop ? '循环' : '单次'} · {clip.root_motion}</span>
              </li>
            ))}
          </ul>
          <p className="character-animation-warning">
            滑步检查为启发式；当前自动结果：{report.automated_outcome}，不等同于人工批准。
          </p>
        </>
      )}
    </EditorStateFrame>
  );
}
