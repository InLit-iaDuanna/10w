import { useState, type CSSProperties } from 'react';
import { useMutation } from '@tanstack/react-query';
import type { components } from '../lab-api';
type S = components['schemas'];

export function VfxLabPanel({ fixture, template, event, api, onProposal, initialDraft, onDraftChange }: {
  fixture: S['VfxShaderRecipe']; template: 'home' | 'warehouse'; event: string; onProposal: () => void; initialDraft?: S['Draft']; onDraftChange?: (draft: S['Draft']) => void;
  api: { evaluate: (draft: S['Draft']) => Promise<S['Evaluation']>; propose: (draft: S['Draft']) => Promise<S['Proposal']> };
}) {
  const [draft, setDraft] = useState<S['Draft']>(initialDraft ?? { template, event,
    parameters: fixture.parameters as S['Draft']['parameters'], quality_tier: fixture.quality_tier,
    particle_count: fixture.particle_count, estimated_overdraw_layers: fixture.estimated_overdraw_layers,
    estimated_screen_coverage_percent: fixture.estimated_screen_coverage_percent, binding_enabled: false });
  const evaluation = useMutation({ mutationFn: (value: S['Draft']) => api.evaluate({ ...value, template, event }) });
  const proposal = useMutation({ mutationFn: (value: S['Draft']) => api.propose({ ...value, template, event }), onSuccess: onProposal });
  const busy = evaluation.isPending || proposal.isPending;
  const update = (next: S['Draft']) => { setDraft(next); onDraftChange?.(next); evaluation.reset(); proposal.reset(); };
  const style = { '--glow-color': String(draft.parameters.color), '--glow-opacity': Number(draft.parameters.intensity),
    '--pulse-duration': `${1 / Number(draft.parameters.pulse_hz)}s`, '--edge-width': `${draft.parameters.edge_width_px}px` } as CSSProperties;
  return <div className="module-grid"><div className="editor-main">
    <div className="section-heading"><h2>{fixture.title_zh}</h2><span className="badge mock">mock · CSS 示意</span></div>
    <div className={`vfx-stage ${draft.binding_enabled ? 'effect-enabled' : ''}`} style={style}>
      <div className="vfx-object"><div className="door-handle" /></div>
      <span>{draft.binding_enabled ? '可选高亮已启用 · 仅示意' : '事件高亮关闭 · 不影响主线'}</span>
    </div>
    <p className="muted">颜色、强度、频率与边缘宽度影响示意图。粒子、overdraw、柔和粒子需真实渲染验证，不在此模拟。</p>
    <div className="actions"><button className="primary" disabled={busy} onClick={() => evaluation.mutate(draft)}>{evaluation.isPending ? '计算中…' : '校验配方与预算'}</button>
      <button disabled={busy} onClick={() => proposal.mutate(draft)}>创建特效配方提案</button></div>
    {evaluation.data && <div className="notice"><strong>配方有效 · mock 预览计划</strong><p>{evaluation.data.message}</p>
      <p>{evaluation.data.preview.passes.join(' → ')} · {evaluation.data.preview.frame_count} 帧计划 / seed {evaluation.data.preview.seed}</p>
      {evaluation.data.preview.warnings.length ? evaluation.data.preview.warnings.map(item => <p className="warning-text" key={item.code}>{item.message_zh}（{item.actual} / {item.allowed}）</p>) : <p className="success-text">当前估算未超出所选画质预算。</p>}</div>}
    {proposal.data && <p className="notice success">特效提案已进入审批列表；未执行发布或渲染。</p>}
    {(evaluation.error || proposal.error) && <p className="notice error" role="alert">{(evaluation.error || proposal.error)?.message}</p>}
    <details className="provenance"><summary>查看内置配方来源</summary><pre>{JSON.stringify(fixture.provenance, null, 2)}</pre><p>来源仅描述内置 mock 配方，不声称当前编辑已发布。</p></details>
  </div><fieldset className="inspector" disabled={busy}><legend>配方参数</legend>
    {fixture.parameter_specs.map(spec => <label key={spec.key}>{spec.label_zh}
      {spec.kind === 'boolean' ? <input type="checkbox" checked={Boolean(draft.parameters[spec.key])} onChange={e => update({ ...draft, parameters: { ...draft.parameters, [spec.key]: e.target.checked } })} /> :
        <input type={spec.kind === 'color' ? 'color' : 'number'} value={String(draft.parameters[spec.key])} min={spec.minimum ?? undefined} max={spec.maximum ?? undefined} step={spec.step ?? undefined} onChange={e => update({ ...draft, parameters: { ...draft.parameters, [spec.key]: spec.kind === 'color' ? e.target.value : Number(e.target.value) } })} />}
    </label>)}
    <h3>画质与估算预算</h3><label>画质档位<select value={draft.quality_tier} onChange={e => update({ ...draft, quality_tier: e.target.value as S['QualityTier'] })}><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label>
    {(['particle_count', 'estimated_overdraw_layers', 'estimated_screen_coverage_percent'] as const).map((key, i) => <label key={key}>{['粒子数量', '估算 overdraw 层数', '估算屏幕覆盖率 %'][i]}<input type="number" min="0" step={i === 0 ? 1 : .1} value={draft[key]} onChange={e => update({ ...draft, [key]: Number(e.target.value) })} /></label>)}
    <label className="toggle"><input type="checkbox" checked={draft.binding_enabled} onChange={e => update({ ...draft, binding_enabled: e.target.checked })} />启用当前事件的可选高亮</label>
    <p className="muted">Unity / Render：blocked。审批不执行外部命令。</p>
  </fieldset></div>;
}
