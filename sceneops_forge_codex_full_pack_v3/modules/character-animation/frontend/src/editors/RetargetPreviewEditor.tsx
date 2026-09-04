import type { RetargetPreviewResult, RetargetProfile } from '../api-types';
import EditorStateFrame from '../components/EditorStateFrame';
import type { RetargetPreviewState } from '../editorStates';
import type { EditorProps } from '../types';

export interface RetargetPreviewData {
  profile: RetargetProfile;
  result?: RetargetPreviewResult;
}

export default function RetargetPreviewEditor({ runtime, localState }: EditorProps<RetargetPreviewState, RetargetPreviewData>) {
  return (
    <EditorStateFrame title="重定向预览" state={runtime}>
      {({ profile, result }) => (
        <>
          <dl className="character-animation-grid">
            <dt>Profile</dt><dd>{profile.retarget_profile_id}</dd>
            <dt>源 Rig</dt><dd>{profile.source_rig_version_id}</dd>
            <dt>目标 Rig</dt><dd>{profile.target_rig_version_id}</dd>
            <dt>骨骼映射</dt><dd>{profile.mappings.length}</dd>
            <dt>固定相机同步</dt><dd>{localState.synchronizeCamera ? '开启' : '关闭'}</dd>
            <dt>预览</dt><dd>{result?.preview?.artifact_uri ?? '尚未捕获'}</dd>
            <dt>序列证据</dt><dd>{result?.preview ? `${result.preview.frame_count} 帧 / ${result.preview.duration_seconds.toFixed(2)} 秒` : '无'}</dd>
          </dl>
          {!result ? <p className="character-animation-warning">重定向集成不可用时保留 Profile 检查，不生成伪 Live 预览。</p> : null}
        </>
      )}
    </EditorStateFrame>
  );
}
