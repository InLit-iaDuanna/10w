import * as React from 'react';
import { useMutation } from '@tanstack/react-query';
import type { LabJob, LabState, RenderLabApi } from './api';
import { SamplePreview } from './SamplePreview';

export function ComparisonPanel({ job, api }: { job: LabJob; api: RenderLabApi }) {
  const [before, setBefore] = React.useState('beauty');
  const [after, setAfter] = React.useState(job.variants[0]?.variant_id ?? 'beauty');
  const [mask, setMask] = React.useState(true);
  const compare = useMutation({ mutationFn: () => api.compare(job.job.job_id, before, after) });
  const choices = [{ id: 'beauty', label: '原始 Beauty' }, ...job.variants.map(v => ({ id: v.variant_id, label: job.images[v.variant_id].label }))];
  if (!job.aovs.length) return <Empty />;
  function selection(which: 'before' | 'after', value: string) {
    compare.reset(); which === 'before' ? setBefore(value) : setAfter(value);
  }
  return <div className="rl-panel">
    <div className="rl-view-toolbar"><div><h2>固定相机 · 变体比较</h2><p>相同视角，检查光照差异与门体保护区。</p></div>
      <label className="rl-check"><input type="checkbox" checked={mask} onChange={e => setMask(e.target.checked)} />显示保护区</label></div>
    <div className="rl-image-pair">{(['before', 'after'] as const).map(side => <div key={side}>
      <label>{side === 'before' ? '比较基准' : '比较候选'}<select value={side === 'before' ? before : after}
        disabled={compare.isPending} onChange={e => selection(side, e.target.value)}>
        {choices.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
      </select></label>
      <SamplePreview image={job.images[side === 'before' ? before : after]} mask={mask} />
    </div>)}</div>
    <div className="rl-actions"><button className="rl-primary" disabled={compare.isPending} onClick={() => compare.mutate()}>计算本地样本差异</button><span>256 个固定单通道像素 · 不启动渲染</span></div>
    {compare.error && <p role="alert" className="rl-error">{compare.error.message}</p>}
    {compare.data && <div className="rl-metrics">
      <div><span>平均绝对差异</span><strong>{(compare.data.comparison.metrics.mean_absolute_difference * 100).toFixed(2)}%</strong></div>
      <div><span>变化像素比例</span><strong>{(compare.data.comparison.metrics.changed_pixel_ratio * 100).toFixed(2)}%</strong></div>
      <div><span>门体保护区</span><strong>{compare.data.comparison.protected_regions.every(r => r.passed) ? '✓ 未超阈值' : '超出阈值'}</strong></div>
    </div>}
    <p className="rl-help">此处测量固定 mock 样本的亮度差异。结果不代表真实渲染验证或艺术质量。</p>
  </div>;
}

export function AovPanel({ job }: { job: LabJob }) {
  const [pass, setPass] = React.useState('beauty');
  const aov = job.aovs.find(a => a.pass_type === pass);
  if (!job.aovs.length) return <Empty />;
  return <div className="rl-panel"><h2>AOV 通道</h2><p>固定 mock 通道，绑定场景和相机版本。</p>
    <div className="rl-pills">{job.aovs.map(a => <button key={a.pass_type} aria-pressed={pass === a.pass_type} onClick={() => setPass(a.pass_type)}>{a.pass_type}</button>)}</div>
    {aov && <div className="rl-aov-detail"><SamplePreview image={job.images[pass]} />
      <dl><dt>Artifact ID</dt><dd>{aov.artifact.artifact_id}</dd><dt>相机</dt><dd>{aov.scene.camera_id} / {aov.scene.camera_version}</dd>
        <dt>模式</dt><dd>MOCK</dd><dt>缓存规划</dt><dd>{job.job.cache_plan.reasons[pass as keyof typeof job.job.cache_plan.reasons]}</dd>
        <dt>说明</dt><dd>16×16 固定单通道教学样本，Normal 为示意而非真实法线向量。</dd></dl></div>}
  </div>;
}

export function ProvenancePanel({ job }: { job: LabJob }) {
  if (!job.variants.length) return <Empty />;
  return <div className="rl-panel"><h2>来源链</h2><p>从场景身份，到配方、工作流、样本与审批记录。</p>
    <ol className="rl-trace">
      <li><strong>场景 / 固定相机</strong><code>{job.job.scene.scene_id} · {job.job.scene.scene_version}</code><code>{job.job.scene.camera_id} · {job.job.scene.camera_version}</code></li>
      <li><strong>配方 / 任务</strong><code>{job.recipe.recipe_id}@{job.recipe.version}</code><code>{job.job.job_id}</code></li>
      <li><strong>请求的 AI 配置（未执行）</strong><code>{job.input.ai_provider} · {job.input.ai_model}</code><span>实际样本来源仍是 deterministic-local-fixture。</span></li>
      {job.variants.map(variant => <li key={variant.variant_id}><strong>{job.images[variant.variant_id].label} · MOCK</strong>
        <dl><dt>Provider</dt><dd>{variant.provenance.provider}</dd><dt>Workflow</dt><dd>{variant.provenance.workflow_reference}</dd>
          <dt>Model</dt><dd>{variant.provenance.model_reference}</dd><dt>Seed（记录值）</dt><dd>{variant.provenance.seed}</dd>
          <dt>提示词</dt><dd>{variant.provenance.prompt}</dd><dt>负向约束</dt><dd>{variant.provenance.negative_prompt}</dd>
          <dt>产物 / 源版本</dt><dd>{variant.output.artifact_id} / {variant.output.source_version}</dd>
          <dt>审批</dt><dd>{variant.approval_state} · {variant.approved_by ?? '待人工确认'}</dd></dl>
        <details><summary>完整来源与审批 JSON</summary><pre>{JSON.stringify(variant, null, 2)}</pre></details>
      </li>)}
    </ol></div>;
}

export function ProposalPanel({ job, api, busy, mutate }: {
  job: LabJob; api: RenderLabApi; busy: boolean; mutate: (request: () => Promise<LabState>) => void;
}) {
  const [variantId, setVariantId] = React.useState(job.variants[0]?.variant_id ?? '');
  const [intensity, setIntensity] = React.useState(850);
  const [rationale, setRationale] = React.useState('增加门廊灯强度，使目标更清晰，并保持门体不变。');
  const variant = job.variants.find(v => v.variant_id === variantId);
  if (!job.variants.length) return <Empty />;
  return <div className="rl-panel"><h2>审批与写回提案</h2><p>先确认变体，再审阅可编辑参数。本页只操作隔离演示记录。</p>
    <div className="rl-proposal-compose"><div><label>候选变体<select value={variantId} onChange={e => setVariantId(e.target.value)}>
      {job.variants.map(v => <option key={v.variant_id} value={v.variant_id}>{job.images[v.variant_id].label}</option>)}</select></label>
      {variant && <><p>变体审批：<strong>{variant.approval_state === 'approved' ? '已审批' : '等待审批'}</strong></p>
        <button disabled={busy || variant.approval_state === 'approved'} onClick={() => mutate(() => api.approveVariant(job.job.job_id, variantId))}>确认此 mock 变体</button></>}
    </div><form onSubmit={e => { e.preventDefault(); mutate(() => api.propose(job.job.job_id, { variant_id: variantId, intensity, rationale })); }}>
      <label>灯光强度：600 → {intensity}<input type="number" required min="0" max="10000" value={intensity} onChange={e => setIntensity(Number(e.target.value))} /></label>
      <label>修改理由<textarea required maxLength={1000} rows={2} value={rationale} onChange={e => setRationale(e.target.value)} /></label>
      <button className="rl-primary" disabled={busy || variant?.approval_state !== 'approved'}>生成写回提案</button>
    </form></div>
    {!job.proposals.length && <p className="rl-help">还没有提案。确认候选变体后，可生成灯光强度修改提案。</p>}
    {job.proposals.map(proposal => <article className="rl-proposal" key={proposal.proposal_id}>
      <div className="rl-section-heading"><strong>{proposal.approval_state === 'approved' ? '✓ 提案已审批' : '◇ 等待提案审批'}</strong><span className="rl-mode">工程写回 BLOCKED</span></div>
      <code>{proposal.proposal_id}</code><dl><dt>对象 / 属性</dt><dd>{proposal.operations[0].target_object_id} / {proposal.operations[0].property}</dd>
        <dt>参数变化</dt><dd>{String(proposal.operations[0].previous_value)} → {String(proposal.operations[0].proposed_value)}</dd>
        <dt>源版本</dt><dd>{proposal.base_scene_version}</dd><dt>理由</dt><dd>{proposal.rationale}</dd>
        <dt>预期效果</dt><dd>{proposal.expected_result}</dd><dt>验证计划</dt><dd>{proposal.validation_plan}</dd>
        <dt>回滚计划</dt><dd>{proposal.rollback_plan}</dd></dl>
      <button disabled={busy || proposal.approval_state === 'approved'} onClick={() => mutate(() => api.approveProposal(job.job.job_id, proposal.proposal_id))}>审批此本地提案</button>
      <details><summary>ChangeSet 与审批快照</summary><pre>{JSON.stringify(proposal, null, 2)}</pre></details>
    </article>)}
    <p className="rl-help">已审批不等于已写回。本入口不注册工程执行接口；真实执行仍需权威审批验证器与 Blender / Unity 适配器。</p>
  </div>;
}

function Empty() { return <div className="rl-empty"><h2>任务尚未载入样本</h2><p>请在队列中选择「载入固定样本」，再进行审阅。</p></div>; }
