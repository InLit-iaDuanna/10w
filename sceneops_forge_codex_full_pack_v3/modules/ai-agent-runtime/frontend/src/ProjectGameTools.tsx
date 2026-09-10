import {useState, type ReactNode} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {agentTasks,agentTaskKeys,type AgentTask} from './client';
import {AgentTaskActivity,TaskCard,GameRuntimePanel} from './AgentTaskWorkbench';
import {SourceIcon} from './SourceIcon';
import './project-game-tools.css';
export function ProjectProgressTool({projectId}:{projectId:string|null}) {
 return <section className="project-game-tool"><header><SourceIcon name="check"/><div><h2>制作进度</h2><p>任务状态、执行记录与问题处理</p></div></header>{projectId?<ProgressContent key={projectId} projectId={projectId}/>:<div className="project-game-empty">先从右上角选择项目。</div>}</section>;
}
const taskLabels:Record<string,string>={awaiting_authorization:'待确认',queued:'排队中',running:'执行中',review_required:'待审阅',completed:'已完成',failed:'执行失败',needs_approval:'需要处理',blocked:'受阻',cancelled:'已取消',interrupted:'已中断',cancel_pending:'正在停止'};
function ProgressContent({projectId}:{projectId:string}) {
 const [archived,setArchived]=useState(false);
 const query=useQuery({queryKey:[...agentTaskKeys.list(projectId),'progress',archived],queryFn:({signal})=>agentTasks.progress(projectId,archived,signal),retry:false,refetchInterval:5000});
 const tasks=[...(query.data?.tasks??[])].sort((a,b)=>b.created_at.localeCompare(a.created_at));
 return <div className="project-progress-scroll">{!archived&&<AgentTaskActivity projectId={projectId} tasks={tasks}/>}
 <div className="project-progress-heading"><h3>{archived?'已归档':'任务记录'} <small>{tasks.length}</small></h3><button type="button" aria-pressed={archived} onClick={()=>setArchived(!archived)}>{archived?'返回任务记录':'查看已归档'}</button></div>
 {query.isPending&&<p role="status">读取任务…</p>}{query.error&&<p role="alert">{query.error.message}<button onClick={()=>void query.refetch()}>重试</button></p>}
 {!query.isPending&&!query.error&&!tasks.length&&<div className="project-game-empty">{archived?'还没有归档的任务。':'当前没有待显示的任务，历史记录可在已归档中查看。'}</div>}
 {tasks.map(task=><ProgressEntry key={task.id} task={task}/>)}
 </div>;
}
function ProgressEntry({task}:{task:AgentTask}) {
 const [expanded,setExpanded]=useState(false); const cache=useQueryClient();
 const archive=useMutation({mutationFn:()=>agentTasks.archive(task.id,{archived:!task.archived}),onSuccess:()=>cache.invalidateQueries({queryKey:['agent-tasks']})});
 const active=['queued','running','cancel_pending'].includes(task.status)||task.owner_pid!=null;
 return <article className="project-progress-record"><details className="project-progress-entry" onToggle={event=>setExpanded(event.currentTarget.open)}><summary><span><strong>{task.goal}</strong><small>{task.authorization_card.card_id??'项目任务'} · {new Date(task.created_at).toLocaleString()}</small></span><em data-state={task.status}>{taskLabels[task.status]??task.status}</em></summary>{expanded&&<TaskCard task={task}/>}</details>
 <div className="project-progress-actions"><button type="button" disabled={archive.isPending||(!task.archived&&active)} title={active&&!task.archived?'任务结束或停止后可归档':task.archived?'恢复到任务记录':'归档这条任务记录'} onClick={()=>archive.mutate()}>{archive.isPending?'处理中…':task.archived?'恢复':'归档'}</button>{archive.error&&<span role="alert">{archive.error.message}</span>}</div></article>;
}
export function ProjectGameTool({projectId,preferredCardId,preferredTaskId}:{projectId:string|null;preferredCardId?:string;preferredTaskId?:string}) {
 if(!projectId)return <div className="project-game-empty">先从右上角选择项目，再打开试玩。</div>;
 return <ProjectGameContent key={`${projectId}/${preferredTaskId??preferredCardId??''}`} projectId={projectId} preferredCardId={preferredCardId} preferredTaskId={preferredTaskId}/>;
}
function ProjectGameContent({projectId,preferredCardId,preferredTaskId}:{projectId:string;preferredCardId?:string;preferredTaskId?:string}) {
 const [selected,setSelected]=useState('');
 const query=useQuery({queryKey:agentTaskKeys.list(projectId),queryFn:({signal})=>agentTasks.list(projectId,signal),retry:false,refetchInterval:5000});
 const tasks=(query.data?.tasks??[]).filter(task=>task.authorization_card.allow_game_execution&&task.grant).sort((a,b)=>b.created_at.localeCompare(a.created_at));
 const task=tasks.find(item=>item.id===(selected||preferredTaskId))??tasks.find(item=>item.authorization_card.card_id===preferredCardId)??tasks[0];
 return <section className="project-game-tool project-game-browser" aria-label="游戏预览">
 {query.isPending&&<div className="project-game-empty" role="status">读取可试玩任务…</div>}
 {query.error&&<div className="project-game-empty" role="alert">{query.error.message}<button onClick={()=>void query.refetch()}>重试</button></div>}
 {task?<GameTaskView key={task.id} task={task} onSelect={setSelected} versionPicker={<select aria-label="试玩版本" value={task.id} onChange={event=>setSelected(event.target.value)}>{tasks.map((item,index)=><option key={item.id} value={item.id}>{index===0?'最新 · ':''}{item.goal.slice(0,28)} · {new Date(item.created_at).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}</option>)}</select>}/>:!query.isPending&&!query.error&&<div className="project-game-empty"><SourceIcon name="code"/><strong>还没有可运行的游戏</strong><p>完成初版制作后，在这里预览。</p></div>}

 </section>;
}
function PreviewIcon({kind}:{kind:'play'|'reload'|'external'}) {
 return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">{kind==='play'?<path d="m8 5 11 7-11 7Z"/>:kind==='reload'?<><path d="M20 7v5h-5"/><path d="M19 12a7 7 0 1 0-2 5M20 12l-3-5"/></>:<><path d="M14 4h6v6M20 4l-9 9"/><path d="M10 5H5v14h14v-5"/></>}</svg>;
}
function GameTaskView({task,versionPicker,onSelect}:{task:AgentTask;versionPicker:ReactNode;onSelect:(id:string)=>void}) {
 const [url,setUrl]=useState<string|null>(null);
 const [reload,setReload]=useState(0);
 const cache=useQueryClient();
 const active=task.owner_pid!=null||['running','queued','cancel_pending'].includes(task.status);
 const start=useMutation({mutationFn:async()=>{
  const state=await agentTasks.gameStatus(task.id);
  if(state.build?.status==='succeeded'&&!state.build.source_stale) {
   const started=await agentTasks.gameOperation(task.id,'preview_start');
   cache.setQueryData(agentTaskKeys.game(task.id),started);
   if(started.preview?.status!=='running')throw new Error(started.preview?.log||'预览启动失败');
  } else if(['project-demo','project-demo-agent'].includes(task.authorization_card.task_profile)) {
   const updated=await agentTasks.updateProjectDemo(task.id);onSelect(updated.id);
  } else throw new Error('请在运行记录中检查并构建此版本。');
  await cache.invalidateQueries({queryKey:['agent-tasks']});
 }});
 return <div className="project-game-content">
  <div className="game-browser-toolbar">
   <span className="game-browser-state" data-running={!!url} title={url?'预览运行中':'预览未运行'}/>
   <div className="game-browser-version">{versionPicker}</div>
   <button type="button" aria-label={url?'刷新游戏':'启动此版本'} title={url?'刷新游戏':'启动此版本'} disabled={start.isPending||(!url&&active)} onClick={()=>url?setReload(value=>value+1):start.mutate()}><PreviewIcon kind={url?'reload':'play'}/></button>
   {url?<a href={url} target="_blank" rel="noopener noreferrer" aria-label="在新窗口打开游戏" title="在新窗口打开"><PreviewIcon kind="external"/></a>:<button disabled aria-label="在新窗口打开游戏"><PreviewIcon kind="external"/></button>}
  </div>
  {start.error&&<div className="game-browser-error" role="alert">{start.error.message}</div>}
  <div className="project-game-canvas">{url?<iframe key={`${url}/${reload}`} src={url} title="游戏试玩" sandbox="allow-scripts allow-same-origin allow-pointer-lock" allow="autoplay; fullscreen; gamepad"/>:<div className="project-game-empty"><PreviewIcon kind="play"/><strong>{start.isPending?'正在启动…':active?'正在制作游戏':'预览尚未启动'}</strong><p>{active?'当前版本准备好后会显示在这里。':'启动所选版本，直接在这里试玩。'}</p><button className="game-browser-start" disabled={start.isPending||active} onClick={()=>start.mutate()}>{start.isPending?'启动中…':'启动预览'}</button></div>}</div>
  <details className="project-game-runtime"><summary>运行记录<span>{url?'运行中':active?'制作中':'未运行'}</span></summary><GameRuntimePanel task={task} onPreviewChange={setUrl} previewWhenRunning/></details>
 </div>;
}
