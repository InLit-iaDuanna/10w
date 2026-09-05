import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { EditorHostProps } from '@sceneops/core-ui';
import { workspaceClient } from '@sceneops/workspace-client';
import { harness, harnessKeys, type ModuleId } from './client';
import { PlanView } from './PlanView';
import { RunView } from './RunView';
import { ModelProfiles } from './ModelProfiles';
import './harness.css';

export type PipelineWorkbenchProps = EditorHostProps & {onDirtyChange?:(dirty:boolean)=>void; onOpenProjects?:()=>void};
export function PipelineWorkbench(props:PipelineWorkbenchProps) {
  if(!props.context.projectId) return <section className="harness-empty">
    <span className="harness-empty-icon" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.6"><rect x="4" y="4" width="9" height="7" rx="2"/><rect x="19" y="21" width="9" height="7" rx="2"/><path d="M8.5 11v10a3.5 3.5 0 0 0 3.5 3.5h7M13 7.5h7a3.5 3.5 0 0 1 3.5 3.5v10"/></svg></span>
    <span className="harness-kicker">生产计划</span><h1>先选择一个项目</h1>
    <p>把目标整理成可审阅的步骤。选择本地项目后，再明确 AI 可以参考的内容。</p>
    <button onClick={props.onOpenProjects}>选择或创建本地项目 <span aria-hidden="true">→</span></button>
    <div className="harness-empty-flow"><span><b>01</b>审阅计划</span><span><b>02</b>确认执行</span><span><b>03</b>观察结果</span></div>
    <small>只有明确确认后，才会发起 AI 请求或执行步骤。</small>
  </section>;
  return <ProjectHarness key={props.context.projectId} {...props}/>;
}

function ProjectHarness(props:PipelineWorkbenchProps) {
  const projectId=props.context.projectId!;
  const cache=useQueryClient();
  const [tab,setTab]=useState<'plan'|'runs'|'capabilities'|'templates'>('plan');
  const [goal,setGoal]=useState('');
  const [constraints,setConstraints]=useState('');
  const [boundedCalls,setBoundedCalls]=useState(false);
  const [modules,setModules]=useState<ModuleId[]>([]);
  const [proposalId,setProposalId]=useState('');
  const [runId,setRunId]=useState('');
  const abort=useRef<AbortController|null>(null);
  const catalog=useQuery({queryKey:harnessKeys.catalog,queryFn:harness.catalog,enabled:!props.suspended});
  const sourceModules=useQuery({queryKey:['workspace-modules'],queryFn:workspaceClient.modules});
  const proposals=useQuery({queryKey:harnessKeys.proposals(projectId),queryFn:()=>harness.proposals(projectId),enabled:!props.suspended});
  const runs=useQuery({queryKey:harnessKeys.runs(projectId),queryFn:()=>harness.runs(projectId),enabled:!props.suspended,
    refetchInterval:query=>!props.suspended && query.state.data?.some(run=>['queued','running','observing','recovering','verifying'].includes(run.state)) ? 1200 : false});
  const templates=useQuery({queryKey:harnessKeys.templates(projectId),queryFn:()=>harness.templates(projectId),enabled:tab==='templates'&&!props.suspended});
  const plan=useMutation({mutationFn:()=>{abort.current=new AbortController();return harness.propose({project_id:projectId,goal:goal.trim(),constraints:constraints.split('\n').filter(Boolean),module_ids:modules,
    budget:{usage_policy:boundedCalls?'bounded_calls':'require_reported',max_metered_calls:4},
    selection:{scene_id:props.context.sceneId,object_ids:props.context.selectedSceneObjectIds,asset_ids:props.context.selectedAssetIds,task_id:props.context.activeTaskId}},abort.current.signal);},
    onSuccess:async proposal=>{await cache.invalidateQueries({queryKey:harnessKeys.proposals(projectId)});setProposalId(proposal.id);setGoal('');setConstraints('');}});
  const dirty=!!goal.trim()||!!constraints.trim()||plan.isPending;
  useEffect(()=>{props.onDirtyChange?.(dirty);},[dirty,props.onDirtyChange]);
  useEffect(()=>()=>{abort.current?.abort();props.onDirtyChange?.(false);},[props.onDirtyChange]);
  const selected=proposals.data?.find(p=>p.id===proposalId) ?? proposals.data?.[0];
  const selectedRun=runs.data?.find(run=>run.id===runId) ?? runs.data?.[0];
  const error=catalog.error??proposals.error??runs.error;
  return <section className="harness-workbench">
    <header className="harness-header"><div><span className="harness-kicker">AI PRODUCTION HARNESS / V5</span><h1>从目标，到可审阅的执行计划。</h1><p>计划、专家决策、运行事实与恢复建议，在同一条记录里。</p></div><span className="harness-state">本地项目</span></header>
    <nav className="harness-tabs" aria-label="AI工作台视图">{([['plan','目标与计划'],['runs','运行记录'],['capabilities','能力与专家'],['templates','模板草稿']] as const).map(([id,label])=><button key={id} aria-pressed={tab===id} onClick={()=>setTab(id)}>{label}</button>)}</nav>
    {error && <p className="harness-notice blocked" role="alert">{error.message} <button onClick={()=>{void catalog.refetch();void proposals.refetch();void runs.refetch();}}>重新读取</button></p>}
    {tab==='plan' && <div className="harness-planning-layout"><aside className="harness-goal-panel"><form onSubmit={event=>{event.preventDefault();if(goal.trim()&&!plan.isPending)plan.mutate();}}>
      <h2>这次想完成什么？</h2><label>制作目标<textarea required rows={5} value={goal} disabled={plan.isPending} onChange={e=>setGoal(e.target.value)} placeholder="描述要实现的玩法、资产或需要解决的问题…"/></label>
      <label>约束与边界<textarea rows={3} value={constraints} disabled={plan.isPending} onChange={e=>setConstraints(e.target.value)} placeholder="每行一条，例如：保留现有角色，不修改原始资产"/></label>
      <details><summary>附带哪些已保存草稿？（{modules?.length??0}）</summary><p>默认只使用当前项目基本信息与明确选择的对象 ID。勾选后才发送对应草稿给 AI。</p>{sourceModules.data?.modules.filter(m=>m.module_id!=='shell').map(item=><label className="harness-check" key={item.module_id}><input type="checkbox" disabled={plan.isPending} checked={modules?.includes(item.module_id as ModuleId)} onChange={e=>setModules(values=>e.target.checked?[...(values??[]),item.module_id as ModuleId]:(values??[]).filter(id=>id!==item.module_id))}/>{item.title}</label>)}</details>
      <label className="harness-check"><input type="checkbox" checked={boundedCalls} disabled={plan.isPending} onChange={event=>setBoundedCalls(event.target.checked)}/>执行时允许用量未知，改按最多 4 次模型调用限制</label>
      {boundedCalls&&<p className="harness-small">费用/Token 硬上限无法完整验证；仍受调用次数、步骤、尝试次数和时间限制。仅影响审阅后开始的运行。</p>}
      <p className="harness-small">生成包含两次模型请求（理解目标、规划步骤），独立于后续运行预算，不启动 Pipeline。整体最多等待 120 秒，可取消；不会自动重试或切换 Mock。</p>
      {plan.isPending?<button type="button" onClick={()=>abort.current?.abort()}>取消生成</button>:<button className="harness-primary" disabled={!goal.trim()||catalog.isError||!catalog.data}>生成 AI 计划</button>}
      {plan.error && <p role="alert">{plan.error.message}</p>}
    </form><div className="harness-history"><h3>已保存计划</h3>{proposals.isPending?<p>正在读取…</p>:proposals.data?.length===0?<p>还没有计划，先从一个目标开始。</p>:proposals.data?.map(p=><button key={p.id} aria-pressed={selected?.id===p.id} onClick={()=>setProposalId(p.id)}>{p.definition.title}<small>{new Date(p.created_at).toLocaleString()} · 尚未执行</small></button>)}</div></aside>
      <div>{selected?<PlanView key={selected.id} proposal={selected} onRun={id=>{setRunId(id);setTab('runs');}}/>:<div className="harness-waiting"><span>01 → 02 → 03</span><h2>先看清步骤，再决定开始。</h2><p>生成后，你会看到所用上下文、能力依赖、专家模型路由，以及当前无法执行的原因。</p></div>}</div></div>}
    {tab==='runs' && <div className="harness-record-layout"><aside className="harness-history"><h3>项目运行</h3>{runs.data?.map(run=><button key={run.id} aria-pressed={selectedRun?.id===run.id} onClick={()=>setRunId(run.id)}>{run.definition.title}<small>{run.state} · {run.execution_mode}</small></button>)}</aside>{selectedRun?<RunView key={selectedRun.id} run={selectedRun} suspended={props.suspended}/>:<div className="harness-waiting"><h2>还没有运行记录</h2><p>审阅计划并明确点击开始后，才会创建执行记录。这里不会自动跑示例。</p></div>}</div>}
    {tab==='capabilities' && <div className="harness-catalog"><p className="harness-notice">{catalog.data?.notice}</p>{catalog.data&&<ModelProfiles catalog={catalog.data}/>}<h2>可调用合同</h2>{catalog.data?.capabilities.map(cap=><article key={cap.id}><div><strong>{cap.title}</strong><code>{cap.id}</code><small>{cap.provider_module_id} · {cap.mode} · {cap.risk}</small></div><span className={`harness-state ${cap.execution_mode==='planned'?'blocked':''}`}>{cap.execution_mode==='planned'?'未接入执行':'按需调用 · 未验证'}</span>{cap.availability_reason&&<p>{cap.availability_reason}</p>}</article>)}<h2>运行专家 · 不是研发代理</h2>{catalog.data?.agents.map(agent=><article key={agent.id}><div><strong>{agent.title}</strong><small>{agent.model_tier} · {agent.allowed_capabilities.join(' / ')}</small><p>{agent.prompt}</p></div></article>)}</div>}
    {tab==='templates' && <div className="harness-catalog"><h2>来自已完成运行的模板草稿</h2><p>模板保留源模式与限制，不自动继承原项目的上下文、审批或权限。</p>{templates.error&&<p role="alert">{templates.error.message}</p>}{templates.data?.length===0&&<p>尚无模板。已完成的运行可以手动沉淀，失败或未执行的计划不能冒充成功模板。</p>}{templates.data?.map(item=><article key={item.id}><div><strong>{item.title}</strong><small>{item.execution_mode} · 来源 {item.source_run_id}</small><p>{item.skill}</p><details><summary>模板内容与复用要求</summary><pre>{JSON.stringify(item,null,2)}</pre></details></div></article>)}</div>}
  </section>;
}
