import {ProductionEntityPanel,type EntityMaterialTarget} from './ProductionEntityPanel';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AgentTaskTimeline } from './AgentTaskWorkbench';
import { agentTasks, agentTaskKeys, type AgentTask } from './client';
import { DemoContentEditor } from './DemoContentEditor';
import './demo-workbench.css';

const taskStatus:Record<AgentTask['status'],string>={awaiting_authorization:'等待确认范围',queued:'排队中',running:'制作中',blocked:'制作受阻',needs_approval:'需要审阅',completed:'制作完成',review_required:'制作结束',failed:'制作失败',cancel_pending:'正在取消',cancelled:'已取消',interrupted:'执行中断'};

function productionRoundStatus(task: AgentTask) {
  if (task.observations.native_production !== true) return taskStatus[task.status];
  if (task.status === 'cancelled') return '本轮已停止 · 可继续修改';
  if (task.status === 'needs_approval' || task.status === 'failed' || task.status === 'interrupted')
    return '本轮未完成 · 可继续修改';
  if (task.status === 'review_required' || task.status === 'completed') return '本轮已完成 · 请试玩';
  return taskStatus[task.status];
}

function productionRoundReason(task: AgentTask) {
  if (task.observations.native_production === true && task.status === 'cancelled')
    return '已保留同一制作会话、当前工程和已有写入；在下方继续输入即可开始下一轮。';
  return task.reason;
}

export type GamePreviewRequest = {taskId:string;url:string};
type Props = {onOpenMaterial?:(target:EntityMaterialTarget)=>void;conversationId?:string;planningCardId?:string;sourceIds?:string[];projectId: string | null; onOpenPreview:(preview:GamePreviewRequest)=>void; onRunPresence?: (present: boolean, running?: {id:string;cancelRequested:boolean})=>void};
export function DemoWorkbench(props: Props) {
  if (!props.projectId) return null;
  return <ProjectDemoWorkbench key={props.projectId} {...props} projectId={props.projectId} />;
}
function ProjectDemoWorkbench({projectId,onRunPresence,onOpenPreview,planningCardId,sourceIds,conversationId,onOpenMaterial}: Props & {projectId:string}) {
  const query = useQuery({queryKey:agentTaskKeys.list(projectId),queryFn:({signal})=>agentTasks.list(projectId,signal),refetchInterval:3000});
  const tasks = (query.data?.tasks ?? []).filter(task=>['project-demo-agent','project-demo'].includes(task.authorization_card.task_profile));
  const ordered=[...tasks].sort((a,b)=>b.created_at.localeCompare(a.created_at));
  const task=ordered[0];
  const productTask=ordered.find(item=>!!item.grant || !!item.observations.demo_authorization_history);
  const running = tasks.find(item=>['queued','running','cancel_pending'].includes(item.status));
  const lastAutoPreview = useRef<string | null>(null);
  const openLatestPreview = useCallback((url:string|null) => {
    if (!url || !task || !['completed','review_required','needs_approval','failed','interrupted','cancelled'].includes(task.status)) return;
    const key = `${task.id}:${url}`;
    if (lastAutoPreview.current === key) return;
    lastAutoPreview.current = key;
    onOpenPreview({taskId:task.id,url});
  }, [onOpenPreview, task?.id, task?.status]);
  useEffect(()=>{onRunPresence?.(tasks.length>0,running ? {id:running.id,cancelRequested:!!running.cancel_requested}:undefined);},[tasks.length,running?.id,running?.cancel_requested,onRunPresence]);
  if(query.isPending) return <p role="status">读取作品…</p>;
  if(query.error) return <p role="alert">作品读取失败：{query.error.message}<button onClick={()=>void query.refetch()}>重试</button></p>;
  if(!task) return null;
  const timeline = <AgentTaskTimeline projectId={projectId} {...(planningCardId ? {cardId:planningCardId,conversationId} : {})} taskProfile={['project-demo-agent','project-demo']} onPreviewChange={openLatestPreview} />;
  if (task.authorization_card.task_profile === 'project-demo-agent' || task.authorization_card.execution_mode === 'agent-full-access') return <section className="demo-workbench demo-conversation" aria-label="游戏制作">
    <header><strong>{productionRoundStatus(task)}</strong><span>{task.provider_model}</span></header>
    {productionRoundReason(task) && <p role={['failed','blocked','interrupted'].includes(task.status) ? 'alert' : 'status'}>{productionRoundReason(task)}</p>}
    {planningCardId && <ProductionEntityPanel task={task} featureId={planningCardId} onOpenMaterial={onOpenMaterial}/> }
    {planningCardId && <ProductionCardSources task={task} sourceIds={sourceIds ?? []} />}
    {timeline}
    <NativeDemoPreview task={task} onOpenPreview={onOpenPreview} />
    {!planningCardId && productTask && !running && (productTask.observations.native_production === true || productTask.authorization_card.execution_mode !== 'agent-full-access') && <DemoProject key={productTask.id} task={productTask} onOpenPreview={onOpenPreview} compact />}
  </section>;
  return <section className="demo-workbench" aria-label="项目作品工作台">
    {task.reason && ['failed','needs_approval','blocked','interrupted'].includes(task.status) && <p role="alert">制作暂未完成：{task.reason}</p>}
    <header><strong>项目作品</strong><span>{task.authorization_card.task_profile === 'project-demo' ? '固定示例' : 'Agent 制作'} · {taskStatus[task.status]}</span></header>
    {productTask && <DemoProject key={productTask.id} task={productTask} onOpenPreview={onOpenPreview} />}
    {!task.grant && !task.observations.demo_pending_authorization && timeline}
    {task.grant && <details><summary>高级：任务详情、授权与执行记录</summary>{timeline}</details>}
  </section>;
}
function ProductionCardSources({task,sourceIds}:{task:AgentTask;sourceIds:string[]}) {
  const content=useQuery({queryKey:agentTaskKeys.content(task.id),queryFn:({signal})=>agentTasks.content(task.id,signal),refetchInterval:3000,retry:false});
  if(content.isPending)return <p role="status">读取卡片关联内容…</p>;
  if(content.error)return <p role="alert">{content.error.message}<button onClick={()=>void content.refetch()}>重新读取</button></p>;
  const sources=(content.data?.sources ?? []).filter(source=>sourceIds.includes(source.id));
  return <section aria-label="卡片关联源码"><h3>当前游戏中的关联内容</h3>
    <p>源码关联当前功能包；已登记对象可用专业工具编辑，行为修改继续使用下方对话。</p>
    {sources.length !== sourceIds.length && <p role="alert">部分关联源码已移除，请重新整理策划后再修改。</p>}
    {sources.map(source=><details key={source.id}><summary>{source.path} · v{source.source_version}</summary><pre style={{maxHeight:320,overflow:'auto'}}><code>{source.content}</code></pre></details>)}
  </section>;
}
export function NativeDemoPreview({task,onOpenPreview}:{task:AgentTask;onOpenPreview:Props['onOpenPreview']}) {
  const game = useQuery({queryKey:agentTaskKeys.game(task.id),queryFn:({signal})=>agentTasks.gameStatus(task.id,signal),refetchInterval:3000,retry:false,enabled:!!task.grant});
  const preview = game.data?.preview;
  return <>
    {preview?.status === 'running' && preview.preview_url && !preview.source_stale &&
      <button className="journey-play-link" type="button" onClick={()=>onOpenPreview({taskId:task.id,url:preview.preview_url!})}>游戏试玩</button>}
    {game.error && <p role="alert">试玩状态读取失败：{game.error.message}</p>}
  </>;
}
function DemoProject({task,onOpenPreview,compact=false}:{task:AgentTask;onOpenPreview:Props['onOpenPreview'];compact?:boolean}) {
  const cache=useQueryClient();
  const game=useQuery({queryKey:agentTaskKeys.game(task.id),queryFn:({signal})=>agentTasks.gameStatus(task.id,signal),refetchInterval:3000,retry:false});
  const content=useQuery({queryKey:agentTaskKeys.content(task.id),queryFn:({signal})=>agentTasks.content(task.id,signal),refetchInterval:3000,retry:false});
  const sessionKey=`sceneops:demo-session:${task.project_id}:${game.data?.workspace_id ?? ''}`;
  const [opened,setOpened]=useState<{id:string;sequence:number}|null>(null);
  const [remembered,setRemembered]=useState<string|null>(null);
  useEffect(()=>{setRemembered(localStorage.getItem(sessionKey));setOpened(null);},[sessionKey]);
  const update=useMutation({mutationFn:()=>agentTasks.updateProjectDemo(task.id),onSettled:()=>cache.invalidateQueries({queryKey:['agent-tasks']})});
  const play=useMutation({mutationFn:(id:string)=>agentTasks.playDemo(task.id,id),
    onSuccess:result=>{setOpened({id:result.candidate_id,sequence:result.sequence});setRemembered(result.candidate_id);localStorage.setItem(sessionKey,result.candidate_id);onOpenPreview({taskId:task.id,url:result.preview_url});}});
  const [renewalId,setRenewalId]=useState(()=>crypto.randomUUID());
  const renewal=useMutation({mutationFn:()=>agentTasks.requestDemoContinuation(task.id,{request_id:renewalId,allow_blender_edit:false}),onSuccess:()=>{setRenewalId(crypto.randomUUID());return cache.invalidateQueries({queryKey:['agent-tasks']});}});
  const consent=useMutation({mutationFn:()=>agentTasks.authorize(task.id,{authorization_card_id:task.authorization_card.id,accept_unknown_cost:true,accept_full_access:false}),onSuccess:()=>cache.invalidateQueries({queryKey:['agent-tasks']})});
  const pendingConsent=task.observations.native_production !== true && task.status==='awaiting_authorization' && !!task.observations.demo_pending_authorization;
  const candidate=game.data?.current_playable_candidate;
  const nativeProduction=task.observations.native_production === true;
  const expired=!nativeProduction && (!task.grant || !!task.grant?.revoked || (!!task.grant?.expires_at && Date.parse(task.grant.expires_at)<=Date.now()));
  const busy=['queued','running','cancel_pending'].includes(task.status) || game.data?.update_state==='building';
  const limit=task.authorization_card.max_model_calls;
  const windowInfo=task.observations.demo_authorization_window;
  const offset=windowInfo && typeof windowInfo==='object' && !Array.isArray(windowInfo) && 'model_calls_start' in windowInfo && typeof windowInfo.model_calls_start==='number' ? windowInfo.model_calls_start:0;
  const windowUsed=task.model_calls_used-offset;
  const actionOffset=windowInfo && typeof windowInfo==='object' && !Array.isArray(windowInfo) && 'actions_start' in windowInfo && typeof windowInfo.actions_start==='number' ? windowInfo.actions_start:0;
  const actionsUsed=task.actions.length-actionOffset;
  const actionLimit=task.grant?.budget?.max_steps;
  const exhausted=!nativeProduction && ((limit!=null && windowUsed>=limit) || (actionLimit!=null && actionsUsed>=actionLimit));
  return <>
    {pendingConsent && <section aria-label="继续制作范围确认"><strong>确认本次继续范围</strong><p>{task.authorization_card.scope}</p><p>{task.authorization_card.cost_notice}</p><p>本次最多 {task.authorization_card.max_model_calls} 次模型请求；累计已使用 {task.model_calls_used} 次。确认后仍需发送具体修改要求。</p><button disabled={consent.isPending} onClick={()=>consent.mutate()}>确认本次继续范围</button>{consent.error && <p role="alert">范围确认失败：{consent.error.message}</p>}</section>}
    {consent.isSuccess && !pendingConsent && <p role="status">范围已确认，继续发送修改要求。</p>}
    {(expired||exhausted) && <p role="alert">{expired?'SceneOps 本次 Agent 编辑权限已结束':'本次制作预算已用尽'}。成果和输入已保留；这不是外部工具的许可证状态。继续制作时需要重新确认有限编辑范围。</p>}
    {(expired||exhausted) && task.status!=='awaiting_authorization' && <button disabled={renewal.isPending} onClick={()=>renewal.mutate()}>申请继续制作范围</button>}
    {renewal.error && <p role="alert">申请范围失败：{renewal.error.message}</p>}
    <details open={compact ? undefined : true}><summary>试玩版本与游戏内容</summary>
    <div className="demo-workbench-actions"><button disabled={!candidate?.id||play.isPending} onClick={()=>{
      if(candidate?.id)play.mutate(candidate.id);
    }}>{candidate ? `试玩版本 ${candidate.sequence}`:'尚无可玩版本'}</button>
    <button disabled={expired||busy||update.isPending} onClick={()=>update.mutate()}>更新作品</button></div>
    <p>编辑源：{content.data?.unbuilt_changes?'有未运行改动':'以当前读取源为准'} · 最新成功候选：{candidate?`版本 ${candidate.sequence}`:'尚无'}</p>
    <p>试玩会话：{opened ? `已打开版本 ${opened.sequence}` : remembered ? `上次打开版本 ${game.data?.build_candidates?.find(item=>item.id===remembered)?.sequence ?? '记录不可读取'}（当前会话未确认）`:'尚未打开'}{candidate?.id && remembered && candidate.id!==remembered ? ' · 新版已就绪，可重新试玩':''}</p>
    {game.data?.build?.source_stale && game.data.update_state!=='building' && <p role="status">内容已改变 · 待更新试玩</p>}
    {game.data?.update_state==='building' && <p role="status">正在构建，已打开试玩保持原版本。</p>}
    {game.data?.update_state==='failed' && <p role="alert">更新失败，旧成功候选仍保留。{game.data.latest_candidate?.failure_code}</p>}
    {[game.error,content.error,update.error,play.error].map((error,index)=>error && <p key={index} role="alert">{error.message}</p>)}
    {content.isPending && <p role="status">读取源内容…</p>}
    {content.error && <button onClick={()=>void content.refetch()}>重读内容</button>}
    {content.data && <details><summary>查看或手动编辑游戏内容</summary><DemoContentEditor key={`${content.data.project_id}:${content.data.workspace_id}`} task={task} content={content.data} viewedCandidateId={opened?.id ?? remembered} unavailable={busy} agentUnavailable={expired||busy||exhausted} /></details>}
    </details>
  </>;
}
