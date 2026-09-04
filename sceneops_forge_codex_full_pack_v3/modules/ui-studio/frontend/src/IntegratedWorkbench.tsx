import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { IntegratedWorkbenchProps, JsonValue } from '@sceneops/core-ui';
import { requestJson } from '@sceneops/api-client';
import { IntegratedDraftForm, useWorkbenchDraft } from '@sceneops/workbench-ui';
import { AudioLabPanel, type AudioLabComponents } from '@sceneops/audio-studio-frontend';
import { VfxLabPanel, type VfxLabComponents } from '@sceneops/vfx-shader-frontend';
import { UiLabPanel } from './editors/UiLabPanel';
import type { components } from './lab-api';
type U = components['schemas'];
type A = AudioLabComponents['schemas'];
type V = VfxLabComponents['schemas'];

export default function IntegratedWorkbench(props: IntegratedWorkbenchProps) {
  const draft = useWorkbenchDraft(props);
  const [tab, setTab] = useState('ui');
  const [notice, setNotice] = useState('');
  const template = props.document.sample_id === 'warehouse-escape' ? 'warehouse' : 'home';
  const event = String(draft.payload.event ?? '');
  const api = useMemo(() => {
    const read = <T,>(path: string) => requestJson<T>(path, { projectId: props.project.project_id, headers: { 'X-Lab-Session': props.project.project_id } });
    const post = <T,>(path: string, body?: unknown) => requestJson<T>(path, { method: 'POST', body, projectId: props.project.project_id, headers: { 'X-Lab-Session': props.project.project_id } });
    return {
      read,
      ui: { check: (body: U['Draft']) => post<U['Check']>('/api/ui/check', body), propose: (body: U['Draft']) => post<U['Proposal']>('/api/ui/proposals', body) },
      audio: { fixture: () => read<A['DemoAudio']>('/api/audio/fixture'), inspectFixture: () => post<A['Inspection']>('/api/audio/inspect-fixture'),
        inspect: (body: A['Upload']) => post<A['Inspection']>('/api/audio/inspect', body), propose: (body: A['BindingDraft']) => post<A['Proposal']>('/api/audio/proposals', body) },
      vfx: { evaluate: (body: V['Draft']) => post<V['Evaluation']>('/api/vfx/evaluate', body), propose: (body: V['Draft']) => post<V['Proposal']>('/api/vfx/proposals', body) },
    };
  }, [props.project.project_id]);
  const uiSample = useQuery({ queryKey: ['integrated-ui-fixture', props.project.project_id, template], queryFn: () => api.read<U['Fixture']>('/api/ui/fixture/' + template), enabled: !!props.document.sample_id, retry: false });
  const vfxSample = useQuery({ queryKey: ['integrated-vfx-fixture', props.project.project_id, template], queryFn: () => api.read<V['VfxShaderRecipe']>('/api/vfx/fixture/' + template), enabled: !!props.document.sample_id, retry: false });
  const ownFixture = useMemo<U['Fixture']>(() => ({
    mode: 'mock', flow: { id: 'ui_' + props.project.project_id, game_template: props.project.project_id, entry_screen_id: 'screen_main', screens: [{ id: 'screen_main', title: '自定义界面', kind: 'hud', localized_text: { 'zh-CN': '' }, next_screen_ids: [], elements: [{ id: 'element_prompt', anchor: 'safe-bottom-center', offset_x: 0, offset_y: 0, width: 400, height: 80 }] }] },
    profile: { name: 'desktop', width: 1280, height: 720, safe_area: { left: 24, right: 24, top: 24, bottom: 24 } },
  }), [props.project.project_id]);
  const proposed = () => setNotice('已记录本地待审提案，未写入引擎。');
  return <>
    <IntegratedDraftForm title="界面、音频与特效" draft={draft} fields={[
      { key: 'event', label: '游戏事件名称' }, { key: 'intent', label: '交互反馈目标', multiline: true },
      { key: 'vfx_notes', label: '自定义特效意图与预算', multiline: true },
    ]}><p>目标对象：{props.context.selectedSceneObjectIds.join('、') || '未选择'}。空项目可直接编辑自己的 UI，并选择自己的 WAV 素材；外部发布始终要求审批。</p></IntegratedDraftForm>
    <nav aria-label="界面音频特效工具">{[['ui', 'UI 流程'], ['audio', '音频素材'], ['vfx', '特效配方']].map(([id, title]) => <button key={id} aria-pressed={tab === id} onClick={() => setTab(id)}>{title}</button>)}</nav>
    {notice && <p role="status">{notice}</p>}
    {tab === 'ui' && <UiLabPanel key={uiSample.data ? props.document.sample_id : 'custom'} fixture={uiSample.data ?? ownFixture} template={template} event={event} api={api.ui} onProposal={proposed}
      mode={props.document.sample_id ? 'mock' : 'planned'} initialDraft={draft.payload.ui as unknown as U['Draft'] | undefined} onDraftChange={value => draft.update({ ui: value as unknown as JsonValue })}/>}
    {tab === 'audio' && <AudioLabPanel template={template} event={event} mixer={String(draft.payload.mixer ?? '')} allowSample={!!props.document.sample_id} api={api.audio} onProposal={proposed} onMixerChange={value => draft.update({ mixer: value })}/>}
    {tab === 'vfx' && (vfxSample.data ? <VfxLabPanel fixture={vfxSample.data} template={template} event={event} api={api.vfx} onProposal={proposed}
      initialDraft={draft.payload.vfx as unknown as V['Draft'] | undefined} onDraftChange={value => draft.update({ vfx: value as unknown as JsonValue })}/> : <p>暂无特效配方。可先保存自己的意图与预算；手动导入 Mock 后可编辑原配方参数。</p>)}
    {(uiSample.error || vfxSample.error) && <p role="alert">样例读取失败：{uiSample.error?.message || vfxSample.error?.message}<button onClick={() => { void uiSample.refetch(); void vfxSample.refetch(); }}>重试样例读取</button></p>}
  </>;
}
