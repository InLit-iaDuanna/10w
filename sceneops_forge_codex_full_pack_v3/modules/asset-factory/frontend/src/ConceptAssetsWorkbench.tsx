import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { labClient, labKeys, advisorKeys, type LabAction } from './labClient';
import './concept-assets.css';

export function ConceptAssetsWorkbench() {
  const [model, setModel] = useState('mock-concept-advisor');
  const [question, setQuestion] = useState('请检查这份概念规格的制作风险，并给出改进建议。');
  const models = useQuery({ queryKey: advisorKeys.models, queryFn: labClient.models, retry: false });
  const advice = useMutation({ mutationFn: labClient.advise });
  const [opened, setOpened] = useState(false);
  const [tab, setTab] = useState('concept');
  const [selected, setSelected] = useState('');
  const [note, setNote] = useState('温暖黄铜与轮廓符合当前方向，未见电子钥匙扣。');
  const [search, setSearch] = useState('');
  const cache = useQueryClient();
  const query = useQuery({ queryKey: labKeys.workspace, queryFn: labClient.read, retry: false });
  const mutation = useMutation({ mutationFn: labClient.action,
    onSuccess: (value, input) => { cache.setQueryData(labKeys.workspace, value); if (input.action === 'compile') setTab('factory'); } });
  const data = query.data;
  const workspace = data?.workspace;
  const variant = workspace?.variants.find(v => v.variant_id === selected) || workspace?.variants.at(-1);
  const act = (action: LabAction['action']) => mutation.mutate({ action, variant_id: variant?.variant_id || '', note });
  const error = query.error || mutation.error;
  const button = (action: LabAction['action'], label: string, disabled = false) =>
    <button disabled={mutation.isPending || disabled} onClick={() => act(action)}>{label}</button>;
  const json = (value: unknown) => <pre>{JSON.stringify(value, null, 2)}</pre>;
  return <main>
    <header><span>SCENEOPS FORGE / 工作台 03</span><b>资产 MOCK · AI 可选模型</b></header>
    {!opened ? <section className="welcome"><small>CONCEPT → ASSET</small><h1>让创意，成为可制作的资产。</h1>
      <p>从黄铜钥匙的概念评审开始，连接风格、生产规格与资产库。</p>
      <form onSubmit={e => { e.preventDefault(); setOpened(true); }}><input aria-label="工作台命令" defaultValue="/ 打开概念与资产工具"/><button>打开工作台 →</button></form>
      <p className="muted">本地业务服务 · 参考素材和 Blender 为 mock · 不调用图像生成或渲染</p></section> : <>
      <nav><button onClick={() => setOpened(false)}>← 对话</button>{[['concept','01 概念板与评审'],['factory','02 规格与生产'],['library','03 资产库与检查']].map(([id,label]) => <button className={tab === id ? 'active' : ''} key={id} onClick={() => setTab(id)}>{label}</button>)}</nav>
      <div className="notice">本地服务实际执行领域操作；图像与资产产物为 mock，AI 文字建议单独显示执行模式。会话仅驻留内存，重启重置。Unity：blocked（未连接）。</div>
      {query.isPending && <p role="status">正在连接本地 API…</p>}
      {error && <div className="error" role="alert">操作失败：{error.message}<button onClick={() => { mutation.reset(); query.refetch(); }}>重新连接 / 刷新</button></div>}
      {mutation.isPending && <p role="status">正在执行本地操作…</p>}
      {workspace && tab === 'concept' && <div className="columns"><section>
        <small>MOODBOARD / {workspace.concept.status}</small><h1>{workspace.concept.subject}</h1><p>{workspace.concept.gameplay_function}</p>
        <div className="actions">{button('generate','载入 Mock 参考方案')}</div>
        {!workspace.variants.length && <p className="empty">还没有参考方案。载入隔离 fixture 后可评审。</p>}
        <div className="variants">{workspace.variants.map(v => <button className={variant?.variant_id === v.variant_id ? 'selected variant' : 'variant'} key={v.variant_id} onClick={() => setSelected(v.variant_id)}>
          <div className="key-drawing" aria-label="Mock 钥匙符号示意图">⚿</div><b>{v.title}</b><span>{v.execution_mode} · {v.status}</span><small>{v.covered_views.join(' / ')}</small></button>)}</div>
        <p className="muted">上图为本地符号示意，不是生成图、真实资产预览或渲染证据。</p>
        {variant && <><h2>概念评审</h2><label>评审证据 / 评论 / 决策理由<textarea value={note} onChange={e => setNote(e.target.value)}/></label>
          <div className="actions">{button('comment','添加评论',!note.trim())}{button('evidence','记录风格符合证据',!note.trim())}{button('reject','拒绝方案',!note.trim())}{button('approve','批准概念',!note.trim())}{button('compile','编译 AssetSpecDraft',variant.status !== 'approved' || !!data?.request)}</div>
          <p className="muted">风格证据是人工声明，置信度 0.7；批准仍检查许可、必需视图和证据。</p>
          {workspace.comments.map(c => <blockquote key={c.comment_id}>{c.body}<small>{c.author_id}</small></blockquote>)}
          <details><summary>风格证据、审批与参考来源</summary>{json({checks:workspace.style_checks,decisions:workspace.decisions,references:workspace.references})}</details></>}
      </section><aside><h2>AI 概念建议</h2>
          <label>模型<select aria-label="AI 模型" value={model} disabled={advice.isPending || models.isPending} onChange={e => { setModel(e.target.value); advice.reset(); }}>
            {(models.data?.models || []).map(m => <option key={m.id} value={m.id} disabled={m.mode === 'blocked'}>{m.id} · {m.provider} · {m.mode}</option>)}
          </select></label><p className="muted">{models.data?.message || '正在读取模型列表…'}</p>
          {models.error && <p role="alert">模型列表读取失败：{models.error.message}<button onClick={() => models.refetch()}>重试</button></p>}
          <label>咨询问题<textarea value={question} onChange={e => setQuestion(e.target.value)}/></label>
          <p className="muted">选择 CodeBuddy 模型并点击后，将发送当前概念规格与问题。仅生成文字建议，不替代人工审批。</p>
          <button disabled={advice.isPending || !question.trim()} onClick={() => advice.mutate({model, question, concept_id:workspace.concept.concept_id})}>{advice.isPending ? '正在等待 CodeBuddy / Mock…' : model === 'mock-concept-advisor' ? '查看 Mock 建议' : '使用 CodeBuddy 生成建议'}</button>
          {advice.error && <p className="error" role="alert">AI 请求失败：{advice.error.message}。可再次点击重试。</p>}
          {advice.data && <article><b>{advice.data.mode} · {advice.data.model}</b><p className="advice" role="status">{advice.data.text}</p></article>}
          <h2>风格规格</h2><dl><dt>比例</dt><dd>{workspace.concept.proportions}</dd><dt>尺寸（米）</dt><dd>{Object.entries(workspace.concept.dimensions).map(([k,v]) => `${k}: ${v}`).join(' · ')}</dd><dt>材质</dt><dd>{workspace.concept.materials.join(' / ')}</dd><dt>预算</dt><dd>{workspace.concept.platform_budget.max_triangles} 三角形 · {workspace.concept.platform_budget.max_texture_size_px}px</dd><dt>风格</dt><dd>{workspace.concept.style_constraints.join('；')}</dd><dt>禁止元素</dt><dd>{workspace.concept.forbidden_elements.join('；')}</dd></dl><details><summary>规格与任务来源</summary>{json(workspace.concept)}</details></aside></div>}
      {data && tab === 'factory' && <section><small>ASSET FACTORY</small><h1>从批准概念到生产规格</h1>
        {!data.handoff ? <p className="empty">先在概念板批准方案，再编译 AssetSpecDraft。</p> : <><p>{data.handoff.spec.display_name} · 预算 {data.handoff.spec.triangle_budget} triangles · mock</p>
          <details open><summary>审阅生产 ChangeSet</summary>{json(data.request?.change_set)}</details>
          <div className="actions">{button('preview','Dry-run 生产预览')}{button('produce','批准此 ChangeSet 并制作 Mock 资产')}</div>
          <details><summary>完整 AssetSpecDraft → AssetSpec 映射</summary>{json(data.handoff)}</details></>}
        <h2>生产队列与结果</h2>{!data.runs.length && <p>暂无运行。Dry-run 只生成 planned 计划。</p>}
        {[...data.runs].reverse().map(run => <article key={run.pipeline_run_id}><h3>{run.state} · {run.execution_mode}</h3><code>{run.pipeline_run_id}</code>
          {run.error_message && <p className="error">{run.error_code}: {run.error_message}</p>}
          <table><thead><tr><th>生产步骤</th><th>状态</th><th>执行模式</th></tr></thead><tbody>{run.steps.map(step => <tr key={step.step_id}><td>{step.kind}</td><td>{step.state}</td><td>{step.execution_mode}</td></tr>)}</tbody></table>
          {run.quality_gates.map(gate => <p key={gate.gate_id}>{gate.status} · {gate.label} — {gate.message}</p>)}
          {run.published_version && <button onClick={() => setTab('library')}>检查已入库 Mock 版本 →</button>}
          <details><summary>完整运行日志与产物来源</summary>{json(run)}</details></article>)}
      </section>}
      {data && tab === 'library' && <section><small>ASSET LIBRARY</small><h1>资产与来源检查</h1><input placeholder="搜索资产名称或 ID" aria-label="搜索资产" value={search} onChange={e => setSearch(e.target.value)}/>
        {!data.assets.length && <p className="empty">资产库为空。编译规格后将登记源资产，生产成功后记录 mock 版本。</p>}
        {data.assets.filter(a => `${a.spec.display_name} ${a.spec.asset_id}`.includes(search)).map(asset => <article key={asset.spec.asset_id}><h2>{asset.spec.display_name}</h2><p>{asset.versions.length} 个版本 · {asset.spec.asset_id}</p><p>来源 {asset.source.origin_uri} · {asset.source.license_name}</p>
          {asset.versions.map(version => <div key={version.asset_version_id}><h3>v{version.version} · {version.execution_mode}</h3><p>{version.asset_version_id}</p><details><summary>尺寸、质量检查、身份与产物</summary>{json(version)}</details></div>)}
          <details><summary>完整资产与使用记录</summary>{json(asset)}</details></article>)}
      </section>}
    </>}
    <footer>概念 / 资产制作 · 127.0.0.1 · MOCK</footer>
  </main>;
}
