import { useCallback, useMemo, useState } from 'react';
import type { IntegratedWorkbenchProps, JsonValue } from '@sceneops/core-ui';
import { requestJson } from '@sceneops/api-client';
import { IntegratedDraftForm, useWorkbenchDraft } from '@sceneops/workbench-ui';
import { CharacterAnimationWorkbench } from './workbench/CharacterAnimationWorkbench';
import { rememberHomeCharacterBundle } from './fixtures/rememberHome';
import type { CharacterBundle } from './api-types';
import type { CharacterAnimationApiPort } from './types';

export default function IntegratedWorkbench(props: IntegratedWorkbenchProps) {
  const draft = useWorkbenchDraft(props);
  const json = String(draft.payload.bundle_json ?? '');
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState<CharacterBundle | null>(() => {
    if (props.document.payload.bundle) return props.document.payload.bundle as unknown as CharacterBundle;
    if (props.document.sample_id === 'remember-home') return structuredClone(rememberHomeCharacterBundle);
    return null;
  });
  const api = useMemo<CharacterAnimationApiPort>(() => ({ post: (path, body) => requestJson(path, { method: 'POST', body, projectId: props.project.project_id }) }), [props.project.project_id]);
  const changed = useCallback((bundle: CharacterBundle) => { draft.update({ bundle: bundle as unknown as JsonValue }); }, [draft.update]);
  function importBundle() {
    try {
      const bundle = JSON.parse(json) as CharacterBundle;
      if (!bundle.character || !bundle.rig || !bundle.skin || !Array.isArray(bundle.clips)) throw new Error('需要 CharacterBundle 的 character、rig、skin 和 clips 字段');
      setLoaded(bundle); draft.update({ bundle: bundle as unknown as JsonValue }); setError('');
    } catch (cause) { setError(String(cause)); }
  }
  return <>
    <IntegratedDraftForm title="角色与动画设计" draft={draft} fields={[
      { key: 'name', label: '角色名称' }, { key: 'source_asset', label: '源资产 ID' },
      { key: 'rig_notes', label: '骨骼与蒙皮要求', multiline: true }, { key: 'animation_notes', label: '片段、循环与根运动要求', multiline: true },
    ]}>
      <details><summary>载入自己的 CharacterBundle 元数据</summary><p>仅载入 JSON 元数据，不加载模型或运行检查；源对象身份与来源记录保持不变。</p><textarea aria-label="CharacterBundle JSON" rows={8} value={json} onChange={event => draft.update({ bundle_json: event.target.value })}/><button type="button" onClick={importBundle}>载入元数据</button>{error && <p role="alert">{error}</p>}</details>
    </IntegratedDraftForm>
    {loaded ? <CharacterAnimationWorkbench key={loaded.character.character_id} api={api} embedded initialBundle={loaded} context={props.context} onBundleChange={changed}/> : <p>尚无角色元数据。可先记录自己的角色设计，再载入已导出的 CharacterBundle；外部生成与重定向未连接。</p>}
  </>;
}
