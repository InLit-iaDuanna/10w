import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AgentTaskTimeline } from './AgentTaskWorkbench';
import { agentTasks, agentTaskKeys, type AgentTask } from './client';
import { DemoContentEditor } from './DemoContentEditor';
import './demo-workbench.css';

const taskStatus:Record<AgentTask['status'],string>={awaiting_authorization:'等待确认范围',queued:'排队中',running:'制作中',blocked:'制作受阻',needs_approval:'需要审阅',completed:'制作完成',review_required:'等待检查',failed:'制作失败',cancel_pending:'正在取消',cancelled:'已取消',interrupted:'执行中断'};

type Props = {projectId: string | null; onRunPresence?: (present: boolean, running?: {id:string;cancelRequested:boolean})=>void};
export function DemoWorkbench(props: Props) {
  if (!props.projectId) return null;
  return <ProjectDemoWorkbench key={props.projectId} {...props} projectId={props.projectId} />;
}
function ProjectDemoWorkbench({projectId,onRunPresence}: Props & {projectId:string}) {
  const query = useQuery({queryKey:agentTaskKeys.list(projectId),queryFn:({signal})=>agentTasks.list(projectId,signal),refetchInterval:3000});
  const tasks = (query.data?.tasks ?? []).filter(task=>['project-demo-agent','project-demo'].includes(task.authorization_card.task_profile));
  const ordered=[...tasks].sort((a,b)=>b.created_at.localeCompare(a.created_at));
  const task=ordered[0];
  const productTask=ordered.find(item=>!!item.grant || !!item.observations.demo_authorization_history);
  const running = tasks.find(item=>['queued','running','cancel_pending'].includes(item.status));
  useEffect(()=>{onRunPresence?.(tasks.length>0,running ? {id:running.id,cancelRequested:!!running.cancel_requested}:undefined);},[tasks.length,running?.id,running?.cancel_requested,onRunPresence]);
  if(query.isPending) return <p role="status">读取作品…</p>;
  if(query.error) return <p role="alert">作品读取失败：{query.error.message}<button onClick={()=>void query.refetch()}>重试</button></p>;
  if(!task) return null;
  const timeline = <AgentTaskTimeline projectId={projectId} taskProfile={['project-demo-agent','project-demo']} />;
  return <section className="demo-workbench" aria-label="项目作品工作台">
    {task.reason && ['failed','needs_approval','blocked','interrupted'].includes(task.status) && <p role="alert">制作暂未完成：{task.reason}</p>}
    <header><strong>项目作品</strong><span>{task.authorization_card.task_profile === 'project-demo' ? '固定示例' : 'Agent 制作'} · {taskStatus[task.status]}</span></header>
    {productTask && <DemoProject key={productTask.id} task={productTask} />}
    {!task.grant && !task.observations.demo_pending_authorization && timeline}
    {task.grant && <details><summary>高级：任务详情、授权与执行记录</summary>{timeline}</details>}
  </section>;
}
function DemoProject({task}:{task:AgentTask}) {
  const cache=useQueryClient();
  const game=useQuery({queryKey:agentTaskKeys.game(task.id),queryFn:({signal})=>agentTasks.gameStatus(task.id,signal),refetchInterval:3000,retry:false});
  const content=useQuery({queryKey:agentTaskKeys.content(task.id),queryFn:({signal})=>agentTasks.content(task.id,signal),refetchInterval:3000,retry:false});
  const sessionKey=`sceneops:demo-session:${task.project_id}:${game.data?.workspace_id ?? ''}`;
  const [opened,setOpened]=useState<{id:string;sequence:number;window:Window}|null>(null);
  const [remembered,setRemembered]=useState<string|null>(null);
  useEffect(()=>{setRemembered(localStorage.getItem(sessionKey));setOpened(null);},[sessionKey]);
  const update=useMutation({mutationFn:()=>agentTasks.updateProjectDemo(task.id),onSettled:()=>cache.invalidateQueries({queryKey:['agent-tasks']})});
  const play=useMutation({mutationFn:async({id,page}:{id:string;page:Window})=>{
    try {const result=await agentTasks.playDemo(task.id,id);page.location.replace(result.preview_url);return {...result,page};}
    catch(error){page.close();throw error;}
  },onSuccess:result=>{setOpened({id:result.candidate_id,sequence:result.sequence,window:result.page});setRemembered(result.candidate_id);localStorage.setItem(sessionKey,result.candidate_id);}});
  const [popupError,setPopupError]=useState('');
  const [renewalId,setRenewalId]=useState(()=>crypto.randomUUID());
  const renewal=useMutation({mutationFn:()=>agentTasks.requestDemoContinuation(task.id,{request_id:renewalId}),onSuccess:()=>{setRenewalId(crypto.randomUUID());return cache.invalidateQueries({queryKey:['agent-tasks']});}});
  const consent=useMutation({mutationFn:()=>agentTasks.authorize(task.id,{authorization_card_id:task.authorization_card.id,accept_unknown_cost:true,accept_full_access:false}),onSuccess:()=>cache.invalidateQueries({queryKey:['agent-tasks']})});
  const pendingConsent=task.status==='awaiting_authorization' && !!task.observations.demo_pending_authorization;
  const candidate=game.data?.current_playable_candidate;
  const expired=!task.grant || !!task.grant?.revoked || (!!task.grant?.expires_at && Date.parse(task.grant.expires_at)<=Date.now());
  const busy=['queued','running','cancel_pending'].includes(task.status) || game.data?.update_state==='building';
  const limit=task.authorization_card.max_model_calls;
  const windowInfo=task.observations.demo_authorization_window;
  const offset=windowInfo && typeof windowInfo==='object' && !Array.isArray(windowInfo) && 'model_calls_start' in windowInfo && typeof windowInfo.model_calls_start==='number' ? windowInfo.model_calls_start:0;
  const windowUsed=task.model_calls_used-offset;
  const actionOffset=windowInfo && typeof windowInfo==='object' && !Array.isArray(windowInfo) && 'actions_start' in windowInfo && typeof windowInfo.actions_start==='number' ? windowInfo.actions_start:0;
  const actionsUsed=task.actions.length-actionOffset;
  const actionLimit=task.grant?.budget?.max_steps;
  const exhausted=(limit!=null && windowUsed>=limit) || (actionLimit!=null && actionsUsed>=actionLimit);
  return <>
    <p>本次范围模型请求 {windowUsed} / {limit ?? '未设上限'}（累计 {task.model_calls_used}） · 制作动作 {actionsUsed} / {actionLimit ?? '见授权范围'} · {task.grant?.expires_at ? `授权至 ${new Date(task.grant.expires_at).toLocaleString()}` : '授权有效期见详情'}</p>
    {pendingConsent && <section aria-label="继续制作范围确认"><strong>确认本次继续范围</strong><p>{task.authorization_card.scope}</p><p>{task.authorization_card.cost_notice}</p><p>本次最多 {task.authorization_card.max_model_calls} 次模型请求；累计已使用 {task.model_calls_used} 次。确认后仍需发送具体修改要求。</p><button disabled={consent.isPending} onClick={()=>consent.mutate()}>确认本次继续范围</button>{consent.error && <p role="alert">范围确认失败：{consent.error.message}</p>}</section>}
    {consent.isSuccess && !pendingConsent && <p role="status">范围已确认，继续发送修改要求。</p>}
    {(expired||exhausted) && <p role="alert">{expired?'授权已到期或撤销':'本次制作预算已用尽'}。成果和输入已保留；请在高级任务详情审阅当前范围，继续制作需要新的明确有限授权。</p>}
    {(expired||exhausted) && task.status!=='awaiting_authorization' && <button disabled={renewal.isPending} onClick={()=>renewal.mutate()}>申请继续制作范围</button>}
    {renewal.error && <p role="alert">申请范围失败：{renewal.error.message}</p>}
    <div className="demo-workbench-actions"><button disabled={!candidate?.id||play.isPending} onClick={()=>{
      if(!candidate?.id)return; const page=window.open('about:blank','_blank');
      if(!page){setPopupError('浏览器阻止了试玩窗口，请允许弹出窗口后重试。');return;}
      page.opener=null;setPopupError('');play.mutate({id:candidate.id,page});
    }}>{candidate ? `试玩版本 ${candidate.sequence}`:'尚无可玩版本'}</button>
    <button disabled={expired||busy||update.isPending} onClick={()=>update.mutate()}>更新 Demo</button></div>
    <p>编辑源：{content.data?.unbuilt_changes?'有未运行改动':'以当前读取源为准'} · 最新成功候选：{candidate?`版本 ${candidate.sequence}`:'尚无'}</p>
    <p>试玩会话：{opened && !opened.window.closed ? `已打开版本 ${opened.sequence}` : remembered ? `上次打开版本 ${game.data?.build_candidates?.find(item=>item.id===remembered)?.sequence ?? '记录不可读取'}（当前会话未确认）`:'尚未打开'}{candidate?.id && remembered && candidate.id!==remembered ? ' · 新版已就绪，可重新试玩':''}</p>
    {game.data?.update_state==='building' && <p role="status">正在构建，已打开试玩保持原版本。</p>}
    {game.data?.update_state==='failed' && <p role="alert">更新失败，旧成功候选仍保留。{game.data.latest_candidate?.failure_code}</p>}
    {[game.error,content.error,update.error,play.error].map((error,index)=>error && <p key={index} role="alert">{error.message}</p>)}
    {popupError && <p role="alert">{popupError}</p>}
    {content.isPending && <p role="status">读取源内容…</p>}
    {content.error && <button onClick={()=>void content.refetch()}>重读内容</button>}
    {content.data && <DemoContentEditor key={`${content.data.project_id}:${content.data.workspace_id}`} task={task} content={content.data} viewedCandidateId={opened?.id ?? remembered} unavailable={busy} agentUnavailable={expired||busy||exhausted} />}
  </>;
}
