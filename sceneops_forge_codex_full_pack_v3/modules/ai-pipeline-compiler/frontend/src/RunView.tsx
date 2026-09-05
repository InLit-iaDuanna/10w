import { useEffect, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { harness, harnessKeys, type Run, type RunAction } from './client';

const labels: Record<string,string> = {queued:'排队中',running:'运行中',observing:'观察中',recovering:'恢复中',verifying:'验证中',completed:'已完成',blocked:'已阻断',failed:'失败',cancelled:'已取消',awaiting_approval:'等待审批',rolled_back:'已回滚',pending:'尚未执行',succeeded:'步骤成功',waiting_approval:'等待审批',assigned:'已分配',evaluating:'评估中',skipped:'未执行'};
export function RunView({run, suspended}: {run: Run; suspended:boolean}) {
  const cache = useQueryClient();
  const abort = useRef<AbortController|null>(null);
  const active = ['queued','running','observing','recovering','verifying'].includes(run.state);
  const events = useQuery({queryKey:harnessKeys.events(run.project_id,run.id), queryFn:()=>harness.events(run.project_id,run.id), enabled:!suspended,
    refetchInterval:active && !suspended ? 1500 : false});
  const action = useMutation({mutationFn:(body:RunAction)=>harness.action(run.project_id,run.id,body),
    onSuccess:()=>cache.invalidateQueries({queryKey:harnessKeys.runs(run.project_id)})});
  const recovery = useMutation({mutationFn:()=>{abort.current = new AbortController();return harness.recover(run.project_id,run.id,abort.current.signal);}});
  const distill = useMutation({mutationFn:()=>harness.distill(run.project_id,run.id,run.definition.title+' · 模板'),
    onSuccess:()=>cache.invalidateQueries({queryKey:harnessKeys.templates(run.project_id)})});
  useEffect(()=>()=>abort.current?.abort(),[]);
  return <article className="harness-run">
    <div className="harness-section-title"><div><small>RUN · {run.id}</small><h2>{run.definition.title}</h2></div><span className={`harness-state ${run.state}`}>{labels[run.state] ?? run.state}</span></div>
    <div className="harness-facts"><span>{run.execution_mode}</span><span>{run.step_runs.filter(s=>s.state==='succeeded').length}/{run.step_runs.length} 步</span><span>{run.duration_seconds.toFixed(1)} 秒</span><span>{run.budget_accounting_complete ? `${run.tokens_used} tokens · $${run.cost_usd.toFixed(4)}` : '用量/费用未完整返回，不是零成本'}</span></div>
    {run.reason && <p className="harness-notice blocked" role="status">{run.reason}</p>}
    <ol className="harness-run-steps">{run.step_runs.map(step=><li key={step.id}>
      <div className="harness-step-line"><strong>{run.definition.stages.flatMap(s=>s.steps).find(s=>s.id===step.step_id)?.title ?? step.step_id}</strong><span className={`harness-state ${step.state}`}>{labels[step.state] ?? step.state}</span></div>
      <small>{step.execution_mode} · {step.attempts.length} 次尝试</small>{step.reason && <p>{step.reason}</p>}
      {step.state==='waiting_approval' && <button disabled={action.isPending} onClick={()=>{if(window.confirm('批准此步骤执行？该批准只适用于当前计划和当前步骤。')) action.mutate({action:'approve',step_id:step.step_id});}}>批准这一步</button>}
      {step.result && <details><summary>实际输出与证据记录</summary><p>{step.result.logs?.join(' · ')}</p><pre>{JSON.stringify(step.result.outputs,null,2)}</pre><ul>{step.result.evidence_refs.map(ref=><li key={ref}><code>{ref}</code></li>)}</ul></details>}
    </li>)}</ol>
    <div className="harness-actions">
      {active && <button disabled={action.isPending} onClick={()=>action.mutate({action:'cancel'})}>取消运行</button>}
      {['failed','blocked','cancelled'].includes(run.state) && <button disabled={action.isPending} onClick={()=>{if(window.confirm('确认重试未成功的步骤？不重跑已成功步骤，仍受预算和权限限制。')) action.mutate({action:'retry'});}}>手动重试原路径</button>}
      {['failed','blocked'].includes(run.state) && <button disabled={recovery.isPending} onClick={()=>recovery.mutate()}>让 AI 分析失败并建议恢复</button>}
      {recovery.isPending && <button onClick={()=>abort.current?.abort()}>取消诊断</button>}
      {run.state==='completed' && <button disabled={distill.isPending} onClick={()=>distill.mutate()}>沉淀为可复用模板草稿</button>}
    </div>
    {(action.error || recovery.error || distill.error) && <p role="alert">{(action.error ?? recovery.error ?? distill.error)?.message}</p>}
    {recovery.data && <section className="harness-notice"><h3>恢复建议 · 尚未执行</h3><strong>{recovery.data.proposal.selected_action}</strong><p>{recovery.data.proposal.reason}</p><ul>{recovery.data.proposal.cause_candidates.map((item,i)=><li key={i}>{item.description}（候选推断）</li>)}</ul><p>不会自动应用。重试需再次点击并经过预算检查；调整模型/上下文后请重新生成计划。</p></section>}
    {distill.data && <p role="status">已保存模板草稿：{distill.data.title}。复用前需要重新绑定项目和上下文。</p>}
    <details><summary>运行事件 · {events.data?.length ?? 0}</summary>{events.error && <p role="alert">{events.error.message}</p>}<ol>{events.data?.map(event=><li key={event.sequence}><time>{new Date(event.occurred_at).toLocaleTimeString()}</time> <code>{event.event_type}</code>{event.step_id && ` · ${event.step_id}`}</li>)}</ol></details>
  </article>;
}
