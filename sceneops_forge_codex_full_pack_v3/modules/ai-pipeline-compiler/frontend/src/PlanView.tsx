import { useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { harness, harnessKeys, type Proposal } from './client';

export function PlanView({proposal, onRun}: {proposal: Proposal; onRun(id: string): void}) {
  const cache = useQueryClient();
  const requestId = useRef(crypto.randomUUID());
  const start = useMutation({mutationFn: () => harness.start(proposal.project_id, proposal.id, requestId.current),
    onSuccess: async run => { await cache.invalidateQueries({queryKey:harnessKeys.runs(proposal.project_id)}); onRun(run.id); }});
  return <article className="harness-plan">
    <div className="harness-section-title"><div><small>PIPELINE PROPOSAL · 尚未执行</small><h2>{proposal.definition.title}</h2></div>
      <span className={`harness-state ${proposal.validation.valid ? 'ready' : 'blocked'}`}>{proposal.validation.valid ? '可审阅并开始' : '执行受阻'}</span></div>
    <p>{proposal.intent.desired_outcome}</p>
    <div className="harness-facts"><span>{proposal.definition.stages.length} 个阶段</span><span>{proposal.definition.stages.reduce((n,s)=>n+s.steps.length,0)} 个步骤</span><span>{proposal.routing.length} 个专家任务</span><span>最多 {proposal.definition.budget.max_duration_seconds}s</span><span>{proposal.definition.budget.usage_policy==='bounded_calls'?`按调用次数限额：${proposal.definition.budget.max_metered_calls}`:'用量未知时停止'}</span></div>
    {proposal.definition.stages.map((stage,index) => <section className="harness-stage" key={stage.id}>
      <h3><span>{String(index+1).padStart(2,'0')}</span>{stage.title}</h3>
      <ol>{stage.steps.map(step => <li key={step.id}><div><strong>{step.title}</strong><code>{step.capability_id}</code></div>
        <small>{step.agent_task ? `${step.agent_task.agent_role} · ${step.model_routing?.tier} · ${step.model_routing?.model}` : '确定性能力'}</small>
        {step.depends_on.length > 0 && <small>依赖：{step.depends_on.join(' → ')}</small>}
        {step.model_routing && <p>{step.model_routing.reason}</p>}
      </li>)}</ol>
    </section>)}
    {proposal.validation.issues.length > 0 && <section className="harness-notice blocked"><h3>需要先解决</h3><ul>{proposal.validation.issues.map((issue,i) => <li key={i}><code>{issue.code}</code> {issue.message}</li>)}</ul></section>}
    {proposal.missing_facts.length > 0 && <section className="harness-notice"><h3>待补充信息</h3><ul>{proposal.missing_facts.map((text,i)=><li key={i}>{text}</li>)}</ul></section>}
    <details><summary>查看目标、上下文来源与验收条件</summary>
      <p>{proposal.intent.goal}</p><ul>{proposal.context.items.map(item=><li key={item.ref.id}>{item.ref.kind} / {item.ref.id} · {item.inclusion_reason} · {item.execution_mode}</li>)}</ul>
      <ul>{proposal.intent.acceptance_criteria.map(item=><li key={item.id}>{item.description} · 尚未验收</li>)}</ul>
    </details>
    <div className="harness-run-cta"><p>开始后仅调用已注册、获授权的能力。模型调用可能消耗额度；未知费用不会显示为已验证的零成本。</p>
      <button disabled={!proposal.validation.valid || start.isPending} onClick={() => {if(window.confirm('确认按这份计划开始？其中的 AI 专家步骤会向当前配置的服务发送已审阅上下文，并可能消耗额度。')) start.mutate();}}>{start.isPending ? '正在提交…' : '审阅完毕，开始运行'}</button>
    </div>
    {start.error && <p role="alert">{start.error.message} <button onClick={()=>start.mutate()}>重试本次提交</button></p>}
  </article>;
}
