import { lazy, Suspense, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import type { AnimationClipSpec, CharacterBundle, CharacterInspectionResult, UnityMappingProposalResult } from '../api-types';
import type { CharacterAnimationApiPort, EditorRuntimeState } from '../types';
import { characterAnimationEditors } from '../editorDefinitions';
import { characterAnimationCommands } from '../commands';
import { rememberHomeCharacterBundle } from '../fixtures/rememberHome';
import './workbench.css';

const editors = characterAnimationEditors.map((definition) => ({ ...definition, Component: lazy(definition.load) }));
const context = {
  projectId: 'project_remember_home', selectedAssetIds: ['asset_homekeeper_source'],
  activeFeatureId: 'feature_key_door_branch', activeTaskId: 'task_player_traversal', activeChangeSetId: null,
};
const permissions = new Set(['character:read', 'animation:read', 'character:write']);
const requestId = () => `lab_${crypto.randomUUID()}`;

export function CharacterAnimationWorkbench({ api }: { api: CharacterAnimationApiPort }) {
  const [bundle, setBundle] = useState<CharacterBundle>(() => structuredClone(rememberHomeCharacterBundle));
  const [active, setActive] = useState('character.editor');
  const [selectedClip, setSelectedClip] = useState(0);
  const [draft, setDraft] = useState(false);
  const [time, setTime] = useState(0);
  const [states, setStates] = useState(() => Object.fromEntries(editors.map((editor) => [editor.id, editor.restoreState(null)])));
  const [prefab, setPrefab] = useState('prefab_homekeeper_lab');
  const [objectId, setObjectId] = useState('sceneops_homekeeper_lab');
  const [controller, setController] = useState('controller_homekeeper_lab');

  async function invokeCommand<TResult>(id: string, input: unknown): Promise<TResult> {
    const command = characterAnimationCommands.find((candidate) => candidate.id === id);
    if (!command) throw new Error(`未知命令：${id}`);
    const available = command.canExecute({ workbench: context, moduleEnabled: true, permissions, integrations: new Set() });
    if (!available.available) throw new Error(available.reason);
    return command.execute({ api, workbench: context }, command.inputSchema.parse(input));
  }
  const inspection = useMutation({ mutationFn: (value: CharacterBundle) => invokeCommand<CharacterInspectionResult>('character.inspect', { request_id: requestId(), bundle: value, mode: 'mock' }) });
  const proposal = useMutation({ mutationFn: () => invokeCommand<UnityMappingProposalResult>('character.unity-mapping.propose', {
    request_id: requestId(), bundle, unity_prefab_id: prefab, unity_game_object_sceneops_id: objectId,
    unity_animator_controller_id: controller, base_unity_version: 'lab_unity_v1',
  }) });
  const comparison = useMutation({ mutationFn: () => invokeCommand('character.version.compare', {
    request_id: requestId(), entity_type: 'clip', base: rememberHomeCharacterBundle.clips[selectedClip], proposed: bundle.clips[selectedClip],
  }) });
  const clip = bundle.clips[selectedClip];
  function editClip(patch: Partial<AnimationClipSpec>) {
    const next = structuredClone(bundle);
    const edited = next.clips[selectedClip];
    const oldId = edited.clip_version_id;
    if (edited.approval.state !== 'draft') {
      edited.previous_version_id = oldId;
      edited.clip_version_id = `clip_lab_${crypto.randomUUID()}`;
      edited.version_number += 1;
      edited.approval = { state: 'draft' };
      edited.provenance.artifact_id = edited.clip_version_id;
      edited.provenance.approval_state = 'draft';
      edited.provenance.execution_mode = 'mock';
      for (const state of next.animator_states ?? []) if (state.clip_version_id === oldId) state.clip_version_id = edited.clip_version_id;
    }
    Object.assign(edited, patch);
    setBundle(next); setDraft(true); inspection.reset(); proposal.reset(); comparison.reset();
  }
  function reset() {
    setBundle(structuredClone(rememberHomeCharacterBundle)); setDraft(false); setTime(0);
    inspection.reset(); proposal.reset(); comparison.reset();
  }
  const report = inspection.data?.report;
  const profile = bundle.retarget_profiles?.[0];
  const data: Record<string, unknown> = {
    'character.editor': { bundle, unityMapping: proposal.data?.mapping },
    'character.rig-inspector': { rig: bundle.rig },
    'character.skin-qa': report ? { skin: bundle.skin, report } : null,
    'animation.timeline': report ? { clips: bundle.clips, report } : null,
    'animation.retarget-preview': profile ? { profile } : null,
    'animation.animator-graph': { states: bundle.animator_states ?? [] },
  };
  const editor = editors.find((candidate) => candidate.id === active);
  const runtime: EditorRuntimeState<unknown> = data[active]
    ? { kind: 'ready', mode: 'mock', data: data[active] }
    : { kind: 'empty', mode: 'mock', message: active === 'animation.retarget-preview' ? '演示数据暂无重定向 Profile。' : '请点击「运行本地检查」加载质量报告。' };
  const busy = inspection.isPending || proposal.isPending || comparison.isPending;
  return <main className="ca-workbench">
    <header><div><span className="ca-eyebrow">SCENEOPS FORGE / 工作台 04</span><h1>角色与动画</h1><p>归家者 · 导入角色的结构检查、动画草稿与引擎交接</p></div><span className="ca-mode">MOCK · 隔离演示数据</span></header>
    <section className="ca-toolbar" aria-label="工作台操作">
      <button disabled={busy} onClick={() => inspection.mutate(bundle)}>{inspection.isPending ? '检查中…' : '运行本地检查'}</button>
      <button disabled={busy} onClick={reset}>重置演示 / 丢弃草稿</button>
      <span>{draft ? '草稿：仅当前页面，刷新后丢失' : '已加载确定性示例'} · 检查算法在本地真实执行，数据模式为 mock</span>
    </section>
    <nav aria-label="角色动画工具">{editors.map((item) => <button key={item.id} aria-current={active === item.id ? 'page' : undefined} onClick={() => setActive(item.id)}>{item.title}</button>)}<button aria-current={active === 'unity' ? 'page' : undefined} onClick={() => setActive('unity')}>Unity 映射提案</button></nav>
    {[inspection.error, proposal.error, comparison.error].filter(Boolean).map((error, index) => <p className="ca-error" role="alert" key={index}>{error?.message}。请检查输入或确认 API 已启动，再重试原操作。</p>)}
    <div className="ca-columns"><section className="ca-main">
      {editor && <Suspense fallback={<p role="status">加载编辑器…</p>}><editor.Component instanceId={`lab-${active}`} contextBinding={{ mode: 'follow-global' }} localState={states[active]} updateLocalState={(patch: object) => setStates((previous) => ({ ...previous, [active]: { ...previous[active], ...patch } }))} runtime={runtime} invokeCommand={invokeCommand}/></Suspense>}
      {active === 'animation.timeline' && <fieldset disabled={busy} className="ca-form"><legend>编辑片段草稿</legend>
        <label>片段<select value={selectedClip} onChange={(event) => { setSelectedClip(Number(event.target.value)); comparison.reset(); setTime(0); }}>{bundle.clips.map((item, index) => <option key={item.clip_version_id} value={index}>{item.name}</option>)}</select></label>
        <label>名称<input value={clip.name} onChange={(event) => editClip({ name: event.target.value })}/></label>
        <label>时长（秒）<input type="number" min="0.01" step="0.1" value={clip.duration_seconds} onChange={(event) => editClip({ duration_seconds: Number(event.target.value) })}/></label>
        <label>根运动<select value={clip.root_motion} onChange={(event) => editClip({ root_motion: event.target.value as AnimationClipSpec['root_motion'] })}><option value="in_place">原地</option><option value="extract">提取</option><option value="apply">应用</option></select></label>
        <label><input type="checkbox" checked={clip.loop} onChange={(event) => editClip({ loop: event.target.checked })}/> 循环播放</label>
        <label>时间游标 {time.toFixed(2)}s<input aria-label="时间游标" type="range" min="0" max={Math.max(0, clip.duration_seconds)} step="0.01" value={time} onChange={(event) => setTime(Number(event.target.value))}/></label>
        {(clip.event_markers ?? []).map((marker, index) => <label key={marker.marker_id}>事件 {marker.name}（秒）<input type="number" step="0.01" value={marker.time_seconds} onChange={(event) => editClip({ event_markers: clip.event_markers?.map((item, position) => position === index ? { ...item, time_seconds: Number(event.target.value) } : item) })}/></label>)}
        <button disabled={busy || clip.approval.state !== 'draft'} onClick={() => comparison.mutate()}>与原始片段比较</button>
        <p>游标仅查看时间位置，不播放 3D 动画。时长修改不会自动缩放采样或事件；重新检查可查看越界证据。草稿不发布新资产，校验值沿用 mock fixture 的占位值，不是内容摘要。</p>
        {comparison.data && <pre>{JSON.stringify(comparison.data, null, 2)}</pre>}
      </fieldset>}
      {active === 'animation.animator-graph' && <section><h2>状态转换关系</h2>{bundle.animator_states?.map((state) => <div className="ca-state" key={state.animator_state_id}><strong>{state.name}</strong><code>{state.clip_version_id}</code>{state.transitions?.map((transition, index) => <p key={index}>→ {bundle.animator_states?.find((target) => target.animator_state_id === transition.target_state_id)?.name ?? transition.target_state_id} · {transition.condition_parameter} {transition.comparison} {transition.threshold} · 混合 {transition.duration_seconds}s</p>)}</div>)}</section>}
      {active === 'animation.retarget-preview' && <section><h2>骨骼映射</h2>{profile?.mappings.map((mapping, index) => <pre key={index}>{JSON.stringify(mapping)}</pre>)}<p className="ca-error">BLOCKED · 重定向与固定相机渲染未连接；此处只查看配置，不生成假预览。</p></section>}
      {active === 'unity' && <fieldset disabled={busy} className="ca-form"><legend>Unity 角色映射提案</legend><p>创建 planned / waiting_approval 的 ChangeSet，不写入 Unity。</p>
        <label>Prefab ID<input value={prefab} onChange={(event) => { setPrefab(event.target.value); proposal.reset(); }}/></label>
        <label>场景对象 ID<input value={objectId} onChange={(event) => { setObjectId(event.target.value); proposal.reset(); }}/></label>
        <label>Animator Controller ID<input value={controller} onChange={(event) => { setController(event.target.value); proposal.reset(); }}/></label>
        <button disabled={busy || draft} onClick={() => proposal.mutate()}>生成待审批提案</button>
        {draft && <p>当前存在未批准草稿。重置演示后可用原始已批准 fixture 生成提案；本工作台不模拟审批。</p>}
        {proposal.data && <><p className="ca-mode">PLANNED · 等待审批 · dry_run</p><pre>{JSON.stringify(proposal.data, null, 2)}</pre></>}
      </fieldset>}
    </section><aside><h2>检查证据</h2>{report ? <><p>自动结果：{report.automated_outcome} · {report.checks.length} 项</p>{report.checks.map((check, index) => <details key={`${check.code}-${index}`}><summary>{check.status} · {check.code}</summary><p>{check.message}</p><pre>{JSON.stringify(check.evidence, null, 2)}</pre>{check.limitation && <p>{check.limitation}</p>}</details>)}</> : <p>尚无当前数据的检查结果。运行本地检查后在此查看原因和采样证据。</p>}<h2>连接状态</h2><p>本地检查：可用</p><p>Unity / Blender / 重定向 / 自动绑定：blocked</p><p>自动检查不等于人工质量批准。此工作台不加载模型、不渲染、不修改生产文件。</p></aside></div>
  </main>;
}
