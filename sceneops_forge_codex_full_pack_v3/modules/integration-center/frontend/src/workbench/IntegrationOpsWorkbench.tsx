import { lazy, Suspense, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { loadLogPanel, type StructuredLogView } from '../../../../observability/frontend/src/index';
import { downloadDiagnostics, operationsKeys, readEvidence, readSnapshot } from './api';
import { EvidenceDialog, IntegrationDetails, labels, Mode, ProgressPanel, WorkerPanel } from './Panels';
import './workbench.css';

const Logs = lazy(loadLogPanel);

export default function IntegrationOpsWorkbench() {
  const [project, setProject] = useState('prj_home_mock');
  const [job, setJob] = useState('');
  const [correlation, setCorrelation] = useState('');
  const [search, setSearch] = useState('');
  const [text, setText] = useState('');
  const [integration, setIntegration] = useState<string | null>(null);
  const [artifact, setArtifact] = useState<string | null>(null);
  const filters = { project_id: project, job_id: job || undefined, correlation_id: correlation || undefined, text: text || undefined };
  const query = useQuery({ queryKey: operationsKeys.snapshot(filters), queryFn: ({ signal }) => readSnapshot(filters, signal) });
  const evidence = useQuery({ queryKey: operationsKeys.evidence(project, artifact || ''),
    queryFn: ({ signal }) => readEvidence(project, artifact!, signal), enabled: !!artifact });
  const diagnostic = useMutation({ mutationFn: () => downloadDiagnostics(project, correlation) });
  const data = query.data;
  const selected = data?.integrations.find(item => item.integration_id === integration);
  function resetFilters() { setJob(''); setCorrelation(''); setSearch(''); setText(''); }
  function selectProject(value: string) { setProject(value); resetFilters(); setIntegration(null); setArtifact(null); diagnostic.reset(); }
  const logs: StructuredLogView[] = (data?.logs || []).map(item => ({
    eventId: item.event_id, emittedAt: item.emitted_at, level: item.level, sourceModule: item.source_module,
    sourceTool: item.source_tool || undefined, message: item.message, mode: item.mode,
    context: { projectId: item.context.project_id, jobId: item.context.job_id || undefined,
      runId: item.context.run_id || undefined, correlationId: item.context.correlation_id, causationId: item.context.causation_id },
    fields: item.fields || {}, artifactLinks: (item.artifact_links || []).map(link => ({ artifactId: link.artifact_id, label: link.label })),
  }));
  return <main className="integration-ops">
    <header className="ops-header"><div className="brand-mark">S<span>F</span></div><div><div className="eyebrow">SCENEOPS FORGE / WORKBENCH 11</div><h1>集成状态与运行日志</h1></div>
      <div className="header-right"><span className="local-dot"/>本地工作台 <Mode/></div></header>
    <div className="demo-banner"><Mode/><span>隔离演示数据 · 不连接外部工具。健康与心跳按固定样例时间解释：2026-09-04 00:01 UTC。</span><details><summary>使用说明</summary><p>先选择项目与任务，再展开集成或日志。点击证据可查看本地脱敏记录；诊断 ZIP 包含当前项目及所选 correlation 的日志和健康摘要。进度不会自动变化。</p></details></div>
    <form className="filters" onSubmit={event => { event.preventDefault(); setText(search); }}>
      <label>项目<select value={project} onChange={event => selectProject(event.target.value)}>
        {(data?.projects || [{ project_id: 'prj_home_mock', title: '归家之路 · 演示项目' }, { project_id: 'prj_warehouse_mock', title: '仓库逃脱 · 演示项目' }]).map(item => <option value={item.project_id} key={item.project_id}>{item.title}</option>)}
      </select></label>
      <label>任务<select value={job} onChange={event => setJob(event.target.value)}><option value="">全部任务</option>{data?.job_ids.map(id => <option key={id}>{id}</option>)}</select></label>
      <label>Correlation<input value={correlation} maxLength={200} placeholder="全部关联链路" onChange={event => setCorrelation(event.target.value)} list="correlations"/></label>
      <datalist id="correlations">{data?.correlation_ids.map(id => <option key={id} value={id}/>)}</datalist>
      <label className="search-label">日志搜索<input value={search} maxLength={200} onChange={event => setSearch(event.target.value)} placeholder="消息或结构化字段…"/></label>
      <button type="submit">搜索</button><button type="button" onClick={resetFilters}>清除</button>
    </form>
    <div className="workbench-toolbar"><span>{query.isFetching ? '正在读取本地快照…' : '本地快照'} <small>集成状态按项目显示 · 任务与链路筛选作用于 Worker、进度和日志</small></span><button onClick={() => query.refetch()} disabled={query.isFetching}>↻ 刷新快照</button></div>
    {query.isPending && <p className="empty" role="status">正在加载工作台…</p>}
    {query.isError && <div className="error-panel" role="alert"><h2>工作台数据暂不可用</h2><p>{query.error.message}</p><button onClick={() => query.refetch()}>重新连接</button><button onClick={resetFilters}>清除筛选</button></div>}
    {data && !query.isError && <>
      <section className="ops-panel integrations"><div className="panel-heading"><h2>集成状态 <small>{data.integrations.length} 个</small></h2><span className="muted">点击查看版本与能力</span></div>
        <div className="integration-grid">{data.integrations.map(item => <button key={item.integration_id} aria-pressed={integration === item.integration_id}
          className={`integration-tile ${integration === item.integration_id ? 'selected' : ''}`} onClick={() => setIntegration(integration === item.integration_id ? null : item.integration_id)}>
          <div className="tile-top"><span className="tool-icon">{item.display_name.slice(0, 2).toUpperCase()}</span><Mode value={item.evidence.mode}/></div>
          <strong>{item.display_name}</strong><span className={`state state-${item.summary_state}`}>● {labels[item.summary_state]}</span>
          <small>v{item.tool_version} · {item.capability_ids.length} 项能力</small>
        </button>)}</div></section>
      {selected && <IntegrationDetails item={selected} onClose={() => setIntegration(null)} onLogs={() => {
        resetFilters(); if (selected.current_job) setJob(selected.current_job.job_id);
        else { setSearch(selected.integration_id); setText(selected.integration_id); }
        document.querySelector('.logs-panel')?.scrollIntoView({ behavior: 'smooth' });
      }}/>}
      <div className="operations-grid"><WorkerPanel workers={data.workers} onJob={setJob}/><ProgressPanel events={data.progress} onJob={setJob}/></div>
      <Suspense fallback={<p className="empty">加载日志编辑器…</p>}><Logs items={logs} onEvidence={setArtifact} onCorrelation={setCorrelation}/></Suspense>
      <section className="ops-panel diagnostic"><div><div className="eyebrow">DIAGNOSTICS</div><h2>诊断摘要 <Mode value={data.summary.mode}/></h2><p>{data.summary.headline}</p><small>导出范围：当前项目{correlation ? ` · ${correlation}` : '的全部关联链路'}。任务、搜索和级别筛选不限制诊断包。</small></div>
        <button className="primary" onClick={() => diagnostic.mutate()} disabled={diagnostic.isPending}>{diagnostic.isPending ? '正在生成…' : '↓ 下载脱敏诊断 ZIP'}</button>
        {diagnostic.isError && <p role="alert" className="error-text">{diagnostic.error.message}</p>}
        {diagnostic.isSuccess && <p role="status">诊断包已生成并触发下载 · MOCK</p>}
      </section>
    </>}
    <footer>集成状态与运行日志 · integration-ops <span>LIVE 真实执行　CACHED 历史真实证据　MOCK 样例　PLANNED 未执行　BLOCKED 无法执行</span></footer>
    {artifact && <EvidenceDialog data={evidence.data} error={evidence.isError} onClose={() => setArtifact(null)}/>}
  </main>;
}
