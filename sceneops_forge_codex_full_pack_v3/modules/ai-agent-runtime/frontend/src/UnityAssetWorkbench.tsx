import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { TaskCard } from './AgentTaskWorkbench';
import { agentTasks, agentTaskKeys, type UnityContentSnapshot } from './client';
import type { components } from './generated/agent-api';

type Snapshot = UnityContentSnapshot;
type Manual = components['schemas']['UnityManualRequest'];
type Instance = Snapshot['instances'][number];
export function UnityAssetWorkbench({sourceTaskId,assetId,assetTitle,sourceVersion,unavailable}:{sourceTaskId:string;assetId:string;assetTitle?:string;sourceVersion:number;unavailable:boolean}) {
  const [taskId,setTaskId]=useState<string|null>(null);
  const cache=useQueryClient();
  const prepare=useMutation({mutationFn:()=>agentTasks.prepareUnityAssetTask(sourceTaskId,{asset_id:assetId,source_version:sourceVersion}),onSuccess:task=>{
    cache.setQueryData(agentTaskKeys.detail(task.id),task);setTaskId(task.id);
  }});
  return <section className="unity-asset-workbench" aria-label="Unity 资产编辑">
    <header className="unity-workbench-heading"><div><h4>Unity 资产往返</h4><p>{assetTitle?.trim()||'所选 Blender 资产'} · Blender 源 v{sourceVersion}</p></div><span className="unity-state-badge">独立 Unity 工程</span></header>
    <p>在 Unity 中继续编辑；再次同步 Blender 模型时，会保留 Prefab、行为和实例参数。</p>
    <details className="unity-technical-details"><summary>查看资产技术信息</summary><p>SceneOps 资产 ID：<code>{assetId}</code></p></details>
    {!taskId && <button disabled={unavailable||prepare.isPending} onClick={()=>prepare.mutate()}>打开 Unity 编辑工作区</button>}
    {prepare.isPending && <p role="status">读取或登记 Unity 编辑目标…</p>}
    {prepare.error && <p role="alert">Unity 工作区准备失败：{prepare.error.message}</p>}
    {taskId && <UnityTask key={taskId} taskId={taskId} sourceVersion={sourceVersion} />}
  </section>;
}
function UnityTask({taskId,sourceVersion}:{taskId:string;sourceVersion:number}) {
  const cache=useQueryClient();
  const task=useQuery({queryKey:agentTaskKeys.detail(taskId),queryFn:({signal})=>agentTasks.get(taskId,signal),refetchInterval:3000,retry:false});
  const content=useQuery({queryKey:agentTaskKeys.unityContent(taskId),queryFn:({signal})=>agentTasks.readUnityContent(taskId,signal),refetchInterval:3000,retry:false});
  const action=useMutation({mutationFn:(body:Manual)=>agentTasks.manualUnityAction(taskId,body),onSuccess:result=>cache.setQueryData(agentTaskKeys.detail(taskId),result),onSettled:()=>cache.invalidateQueries({queryKey:['agent-tasks']})});
  const resume=useMutation({mutationFn:()=>agentTasks.resume(taskId),onSuccess:result=>cache.setQueryData(agentTaskKeys.detail(taskId),result),onSettled:()=>cache.invalidateQueries({queryKey:['agent-tasks']})});
  const value=task.data;
  const window=value?.observations?.demo_authorization_window;
  const fields=window && typeof window==='object' && !Array.isArray(window) ? window as Record<string,unknown> : undefined;
  const offsets=fields?.grant_id===value?.grant?.id ? fields : undefined;
  const actionsUsed=(value?.actions.length ?? 0)-(typeof offsets?.actions_start==='number'?offsets.actions_start:0);
  const callsUsed=(value?.model_calls_used ?? 0)-(typeof offsets?.model_calls_start==='number'?offsets.model_calls_start:0);
  const budget=value?.grant?.budget;
  const exhausted=!!budget && (actionsUsed>=budget.max_steps || callsUsed>=budget.max_metered_calls);
  const active=!exhausted && !!value?.grant && !value.grant.revoked && !!value.grant.expires_at && Date.parse(value.grant.expires_at)>Date.now();
  const busy=action.isPending || !!value && ['running','queued','cancel_pending'].includes(value.status);
  const disabled=!active||busy||!value||!['review_required','completed','failed'].includes(value.status);
  const run=(operation:Manual['operation'])=>action.mutate({request_id:crypto.randomUUID(),operation,...(operation==='import'?{source_version:sourceVersion}:{})});
  const act=(input:Partial<Pick<Manual,'move_x'|'move_z'|'interact'|'duration_frames'>>)=>action.mutate({request_id:crypto.randomUUID(),operation:'act',...input});
  return <>
    {(task.isPending||content.isPending) && <p role="status">读取 Unity 目标…</p>}
    {task.error && <p role="alert">任务读取失败：{task.error.message}<button onClick={()=>void task.refetch()}>重试</button></p>}
    {content.error && <p role="alert">Unity 内容读取失败：{content.error.message}<button onClick={()=>void content.refetch()}>重试</button></p>}
    {value?.status==='awaiting_authorization' && <TaskCard task={value} inline />}
    {value && <section className="unity-access-summary"><strong>SceneOps 编辑权限：{active?'可以继续编辑':exhausted?'本次额度已用完':'本次编辑已结束'}</strong><p>这里只控制工作台和 Agent 是否可以继续写入。Unity 许可证请以 Unity Hub 显示为准。</p><details><summary>查看本次范围与用量</summary><p>已执行 {actionsUsed} / {budget?.max_steps ?? '见范围'} 个动作{value.grant?.expires_at && ` · 本次范围截止 ${new Date(value.grant.expires_at).toLocaleString()}`}</p></details></section>}
    {value?.grant && !active && <button disabled={action.isPending} onClick={()=>run('renew')}>重新确认 Unity 编辑范围</button>}
    {value?.actions.some(item=>item.effect_state==='UNKNOWN') && <button disabled={action.isPending} onClick={()=>run('reconcile')}>核查原操作回执</button>}
    {value?.status==='blocked' && active && <button disabled={resume.isPending} onClick={()=>resume.mutate()}>连接问题解决后继续本次任务</button>}
    {resume.error && <p role="alert">{resume.error.message}</p>}
    {value?.reason && <p role={['failed','blocked','interrupted'].includes(value.status)?'alert':'status'}>{value.reason}</p>}
    {content.data && <>
      <UnityTargetSummary content={content.data}/>
      <div className="demo-workbench-actions">{([['import','同步 Blender 更新'],['inspect','刷新 Unity 状态'],['save','保存 Unity 场景'],['reopen','重新打开已保存场景'],['play','开始试玩'],['stop','结束试玩']] as const).map(([operation,label])=><button key={operation} disabled={disabled||content.data.compiling||(operation==='reopen' && content.data.dirty)||(content.data.playing && operation!=='stop' && operation!=='inspect')} onClick={()=>run(operation)}>{label}</button>)}</div>
      {content.data.playing && <div className="demo-workbench-actions" aria-label="Unity 试玩输入">
        <button disabled={disabled||content.data.compiling} onClick={()=>act({move_x:-1,duration_frames:120})}>向左移动</button>
        <button disabled={disabled||content.data.compiling} onClick={()=>act({move_x:1,duration_frames:120})}>向右移动</button>
        <button disabled={disabled||content.data.compiling} onClick={()=>act({move_z:1,duration_frames:120})}>向前移动</button>
        <button disabled={disabled||content.data.compiling} onClick={()=>act({move_z:-1,duration_frames:120})}>向后移动</button>
        <button disabled={disabled||content.data.compiling} onClick={()=>act({interact:true,duration_frames:1})}>交互</button>
      </div>}
      {content.data.instances.length===0 && <p>尚无已读取的 Unity 实例。</p>}
      {content.data.instances.map((instance,index)=><UnityInstanceEditor key={instance.instance_id} number={index+1} instance={instance} disabled={disabled||content.data!.playing||content.data!.compiling} onAction={body=>action.mutate(body)}/>)}
      <UnityAgentInput disabled={disabled} onAction={body=>action.mutate(body)} />
    </>}
    {busy && <p role="status">Unity 任务执行中…</p>}
    {action.error && <p role="alert">Unity 操作失败：{action.error.message}。编辑输入已保留。{action.variables && <button disabled={disabled} onClick={()=>action.mutate(action.variables!)}>用原请求编号重试</button>}</p>}
    {value?.actions.at(-1)?.state==='failed' && <p role="alert">{value.actions.at(-1)?.reason}</p>}
  </>;
}
function UnityTargetSummary({content}:{content:Snapshot}) {
  const synchronized=content.imported_source_version===content.available_source_version;
  const ready=synchronized && !!content.scene_path && content.instances.length>0 && !content.dirty;
  const headline=content.compiling?'Unity 正在导入或编译':content.playing?'Unity 正在试玩':!synchronized?'Blender 有新版本待同步':ready?'已同步并保存':'Unity 工作区已连接';
  const sceneName=content.scene_path?.split('/').at(-1) ?? '尚未登记';
  return <section className="unity-sync-summary" aria-label="Unity 当前状态">
    <header><strong>{headline}</strong><span>{content.mode==='cached'?'从保存记录读回':'已连接 Unity Editor'}</span></header>
    <div className="unity-summary-grid"><div><small>模型</small><b>{synchronized?`v${content.imported_source_version} 已同步`:`v${content.imported_source_version} → v${content.available_source_version}`}</b></div><div><small>场景</small><b>{sceneName}</b></div><div><small>实例</small><b>{content.instances.length} 个</b></div><div><small>保存状态</small><b>{content.dirty?'有未保存修改':'已保存'}</b></div></div>
    {content.notice && <p role="status">{content.notice}</p>}
    <details className="unity-technical-details"><summary>查看 Unity 技术信息</summary><dl><dt>编辑器</dt><dd>Unity {content.editor_version}</dd><dt>工程</dt><dd><code>{content.project_root}</code></dd><dt>场景</dt><dd><code>{content.scene_path ?? '尚未登记'}</code></dd><dt>资产 ID</dt><dd><code>{content.source_asset_id}</code></dd><dt>回读模式</dt><dd><code>{content.mode} · {content.status}</code></dd></dl></details>
  </section>;
}
function UnityInstanceEditor({number,instance,disabled,onAction}:{number:number;instance:Instance;disabled:boolean;onAction:(body:Manual)=>void}) {
  const [base,setBase]=useState(instance);
  const [position,setPosition]=useState(instance.position);
  const [distance,setDistance]=useState(String(instance.interaction_distance));
  const [requiresKey,setRequiresKey]=useState(instance.requires_key);
  const stale=JSON.stringify(base)!==JSON.stringify(instance);
  return <form className="unity-instance-card" onSubmit={event=>{event.preventDefault();onAction({request_id:crypto.randomUUID(),operation:'edit',instance_id:instance.instance_id,expected:{position:base.position,interaction_distance:base.interaction_distance,requires_key:base.requires_key},position,interaction_distance:Number(distance),requires_key:requiresKey});}}>
    <header><strong>Unity 实例 {number}</strong><span>{requiresKey?'需要钥匙':'无需钥匙'}</span></header>
    <details className="unity-technical-details"><summary>查看实例 ID</summary><code>{instance.instance_id}</code></details>
    {stale && <p role="alert">Unity 实例已变化；输入保留，请读取当前字段后再提交。</p>}
    <div className="demo-fields">{(['X','Y','Z'] as const).map((axis,index)=><label key={axis}>位置 {axis.toUpperCase()}（米）<input type="number" step="any" required value={position[index]} onChange={event=>setPosition(previous=>{const next:Instance['position']=[...previous];next[index]=Number(event.target.value);return next;})}/></label>)}
      <label>交互距离（米）<input type="number" min="0.2" max="10" step="any" required value={distance} onChange={event=>setDistance(event.target.value)}/></label>
      <label>需要钥匙<input type="checkbox" checked={requiresKey} onChange={event=>setRequiresKey(event.target.checked)}/></label>
    </div>
    <button disabled={disabled||stale}>应用单实例字段</button>
    <button type="button" disabled={disabled} onClick={()=>onAction({request_id:crypto.randomUUID(),operation:'focus',instance_id:instance.instance_id})}>在 Unity 中定位实例</button>
    <button type="button" onClick={()=>{setBase(instance);setPosition(instance.position);setDistance(String(instance.interaction_distance));setRequiresKey(instance.requires_key);}}>读取当前字段（替换草稿）</button>
  </form>;
}
function UnityAgentInput({disabled,onAction}:{disabled:boolean;onAction:(body:Manual)=>void}) {
  const [goal,setGoal]=useState('');
  return <form onSubmit={event=>{event.preventDefault();onAction({request_id:crypto.randomUUID(),operation:'agent',goal});}}><label>让 Agent 修改这个 Unity 资产<textarea rows={2} maxLength={4000} placeholder="例如：把第 2 个实例的交互距离改为 1.5 米并保存" value={goal} onChange={event=>setGoal(event.target.value)}/></label><button disabled={disabled||!goal.trim()}>发送 Unity 修改要求</button></form>;
}
