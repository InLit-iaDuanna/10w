import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { experienceApi, experienceEvidenceLabels, type MemoryEvent, type MemoryWrite } from './experience-client';
import { MemorySource } from './MemorySource';
import { MemoryComposer } from './MemoryComposer';
const labels:Record<string,string>={remember:'记忆更新',correct:'记忆更新',restore:'已撤销修改',learn:'本次沉淀',reference:'执行中引用',verify:'验证记录'};
export function MemoryActivity({projectId,originKey,active=false,sourceId}:{projectId:string|null;originKey:string;active?:boolean;sourceId?:string}) {
  const activity=useQuery({queryKey:['experience','activity',projectId,originKey],queryFn:()=>experienceApi.activity(projectId,originKey),retry:false,refetchInterval:query=>active || query.state.data?.pending?5000:false});
  const wasActive=useRef(active);
  useEffect(()=>{if(wasActive.current && !active)void activity.refetch();wasActive.current=active;},[active,activity.refetch]);
  if(activity.error) return <details className="experience-references"><summary>学习状态暂不可用</summary><p role="alert">{activity.error.message}<button onClick={()=>void activity.refetch()}>重试</button></p></details>;
  if(!activity.data) return null;
  return <>{activity.data.events.map(event=><MemoryChange key={event.id} projectId={projectId} originKey={originKey} event={event} sourceId={sourceId}/>)}{activity.data.pending && <details className="experience-references"><summary>待整理</summary><p>新记录尚未完成整理，保存后会在这里更新。</p>{activity.data.batches.map(batch=><p key={batch.id}>{batch.reason || ({running:'正在整理',budget_wait:'等待独立学习预算',failed:'整理失败',paused:'自动学习已暂停'} as Record<string,string>)[batch.status] || '等待整理'}</p>)}</details>}</>;
}
function MemoryChange({projectId,originKey,event,sourceId}:{projectId:string|null;originKey:string;event:MemoryEvent;sourceId?:string}) {
  const cache=useQueryClient(); const [edit,setEdit]=useState<MemoryWrite|null>(null);
  const correctionSource=sourceId ?? (['remember','correct','restore'].includes(event.operation)?event.source_ids[0]:undefined);
  const current=useMutation({mutationFn:async()=>{
    if(event.after){const entry=await experienceApi.entry(projectId,event.after.id);return {intent:'explicit',source_quote:'',project_id:projectId,origin_key:originKey,source_id:correctionSource!,entry_id:entry.id,expected_revision:entry.revision,title:entry.title,content:entry.content,category:entry.memory_category ?? 'fact'} as MemoryWrite;}
    const memory=await experienceApi.projectMemory(projectId!);const reference=memory.references.find(item=>item.id===event.reference?.id);
    if(!reference?.editable)throw new Error('这项项目决定不能在此编辑，请返回原对话修改。');
    return {intent:'explicit',source_quote:'',project_id:projectId,origin_key:originKey,source_id:correctionSource!,reference_id:reference.id,expected_revision:reference.revision,title:reference.title,content:reference.content,category:reference.category} as MemoryWrite;
  },onSuccess:setEdit});
  const undo=useMutation({mutationFn:()=>experienceApi.undo(projectId,event.id,event.after?.revision ?? event.reference!.revision),onSuccess:()=>void cache.invalidateQueries({queryKey:['experience']})});
  return <details className="experience-references memory-change"><summary>{event.resolved_by?'已处理':event.state==='pending'?'待整理':event.state==='failed'?'记忆未保存':labels[event.operation] ?? '记忆变更'} · {event.after?.title ?? event.reference?.title ?? event.before?.title ?? event.proposal?.title ?? '记录'}</summary>
    {event.reason && <p role={event.state==='failed'?'alert':'status'}>{event.reason}</p>}
    <small>{event.after?.scope==='shared'?'通用经验':'当前项目'} · {new Date(event.created_at).toLocaleString('zh-CN')}</small>
    {event.previous_reference && <section><small>修改前 · v{event.previous_reference.revision}</small><p>{event.previous_reference.content}</p></section>}{event.before && <section><small>修改前 · v{event.before.revision}</small><p>{event.before.content}</p></section>}
    {event.state==='saved' && (event.after || event.reference) && <section><small>{event.operation==='verify'?'验证关联版本':event.operation==='reference'?'执行引用版本':'已保存'} · v{event.after?.revision ?? event.reference?.revision}</small><p>{event.after?.content ?? event.reference?.content}</p></section>}
    <div className="experience-editor-actions">{event.state!=='saved' && !event.resolved_by && event.proposal && <button onClick={()=>setEdit({...event.proposal!,intent:'explicit',resolves_event_id:event.id})}>{event.state==='pending'?'查看并确认':'编辑后重试'}</button>}{event.state==='saved' && projectId && (event.after || event.reference?.editable) && correctionSource && <button disabled={current.isPending} onClick={()=>current.mutate()}>纠正此条</button>}{event.state==='saved' && ['remember','correct','restore','learn'].includes(event.operation) && (event.after || event.reference) && <button disabled={undo.isPending || undo.isSuccess} onClick={()=>undo.mutate()}>{undo.isSuccess?'已撤销':undo.isPending?'撤销中…':'撤销修改'}</button>}</div>
    {(event.operation==='verify' || event.operation==='reference') && <p>本次执行证据：{experienceEvidenceLabels[event.evidence_status ?? 'unknown']}</p>}
    {current.error && <p role="alert">无法读取当前版本：{current.error.message}</p>}{undo.error && <p role="alert">未撤销：{undo.error.message}</p>}{edit && <MemoryComposer value={edit} onClose={()=>setEdit(null)}/>}
    <details><summary>来源</summary>{event.source_ids.map(source=><p key={source}><MemorySource source={source}/></p>)}</details>
  </details>;
}
export function MemoryMessage({projectId,originKey,sourceId,text,active=false,correctionSourceId}:{projectId:string|null;originKey:string;sourceId:string;text?:string;active?:boolean;correctionSourceId?:string}) {
  const [editing,setEditing]=useState(false);
  return <div className="memory-message">{text && projectId && <button className="memory-remember" type="button" onClick={()=>setEditing(value=>!value)}>记住</button>}{editing && projectId && <MemoryComposer value={{intent:'explicit',source_quote:'',project_id:projectId,source_id:sourceId,origin_key:originKey,title:(text ?? '').slice(0,80),content:text ?? '',category:'fact'}} onClose={()=>setEditing(false)}/>}<MemoryActivity projectId={projectId} originKey={originKey} active={active} sourceId={correctionSourceId ?? (text?sourceId:undefined)}/></div>;
}
