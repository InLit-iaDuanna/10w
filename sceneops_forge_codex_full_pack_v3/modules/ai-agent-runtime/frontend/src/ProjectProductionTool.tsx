import {useQuery} from '@tanstack/react-query';
import {agentTasks,agentTaskKeys,type AgentTask} from './client';
import {CreationBriefPanel} from './CreationBriefPanel';
import {AgentTaskTimeline} from './AgentTaskWorkbench';

/** Production follows the project's actual native task, including its selected skills. */
export function ProjectProductionTool({projectId,compact=false}:{projectId:string|null;compact?:boolean}) {
  const tasks=useQuery({queryKey:agentTaskKeys.list(projectId??''),queryFn:({signal})=>agentTasks.list(projectId!,signal),enabled:!!projectId,refetchInterval:3000});
  const task=tasks.data?.tasks.find(item=>item.observations.native_production&&!item.archived);
  if(!projectId)return <p>请先选择项目。</p>;
  return <section aria-label="当前项目 AI 制作"><h2>AI 制作与技能</h2>
    <p>读取当前游戏实际使用的制作简报、技能和执行记录。各领域的制作要求通过原项目会话执行。</p>
    {tasks.error&&<p role="alert">{tasks.error.message}</p>}
    {task&&<NativeBrief key={task.id} task={task}/>}
    {!task&&!tasks.isPending&&<p>当前项目尚无原生制作任务。可从策划与制作领域提交制作要求。</p>}
    {!compact&&<AgentTaskTimeline projectId={projectId}/>}
  </section>;
}

function NativeBrief({task}:{task:AgentTask}) {
  const brief=useQuery({queryKey:agentTaskKeys.creationBrief(task.id),queryFn:({signal})=>agentTasks.creationBrief(task.id,signal)});
  if(task.status==='awaiting_authorization')return <CreationBriefPanel task={task}/>;
  return <section><p>执行器：{task.provider_id} · 模型：{task.provider_model??'执行器默认模型'}</p>
    {brief.error&&<p role="alert">{brief.error.message}</p>}
    {brief.data&&<><h3>本次加载的制作技能</h3><ul>{brief.data.selected_skills?.map(id=><li key={id}>{id}</li>)}</ul>
      <details><summary>实际制作简报 · v{brief.data.version}</summary><pre style={{whiteSpace:'pre-wrap'}}>{brief.data.content}</pre></details></>}
  </section>;
}
