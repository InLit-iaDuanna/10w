import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { experienceApi, experienceEvidenceLabels, type MemoryWrite } from './experience-client';
import { MemorySource } from './MemorySource';
import { MemoryComposer } from './MemoryComposer';
import './experience.css';
export function ExperienceReferences({projectId,useKey,exact=true,sourceId}: {projectId:string|null;useKey:string;exact?:boolean;sourceId?:string}) {
  const [edit,setEdit]=useState<MemoryWrite|null>(null);
  const correct=useMutation({mutationFn:(id:string)=>experienceApi.entry(projectId,id),onSuccess:entry=>setEdit({intent:'explicit',source_quote:'',project_id:projectId,origin_key:useKey,source_id:sourceId!,entry_id:entry.id,expected_revision:entry.revision,title:entry.title,content:entry.content,category:entry.memory_category ?? 'fact'})});
  const correctReference=useMutation({mutationFn:(_id:string)=>experienceApi.projectMemory(projectId!),onSuccess:(memory,id:string)=>{const reference=memory.references.find(item=>item.id===id);if(reference?.editable)setEdit({intent:'explicit',source_quote:'',project_id:projectId,origin_key:useKey,source_id:sourceId!,reference_id:reference.id,expected_revision:reference.revision,title:reference.title,content:reference.content,category:reference.category});}});
  const query=useQuery({queryKey:['experience','uses',projectId,useKey,exact],queryFn:()=>experienceApi.uses(projectId,useKey,exact),retry:false,refetchInterval:exact?false:10000});
  const records=(query.data ?? []).filter(record=>record.items.length || record.project_memories?.length || record.failure_reason);
  if(query.error) return <details className="experience-references"><summary>本次依据读取失败</summary><p role="alert">{query.error.message}<button onClick={()=>void query.refetch()}>重试</button></p></details>;
  if(!records.length) return null;
  const titles=records.flatMap(record=>[...(record.project_memories ?? []).map(item=>item.title),...record.items.map(item=>item.title)]);
  return <details className="experience-references"><summary>{titles.length?`本次依据 · ${titles.length} 条`:'本次记忆暂不可用'} <span>{titles.slice(0,2).join('、')}{titles.length>2?'…':''}</span></summary>
    {titles.length>0 && <p className="experience-muted">已提供给本次请求；执行引用与验证结果单独记录。这里保留当时的版本。</p>}
    {correctReference.error && <p role="alert">无法读取项目决定：{correctReference.error.message}</p>}{correct.error && <p role="alert">无法读取当前版本：{correct.error.message}</p>}{edit && <MemoryComposer value={edit} onClose={()=>setEdit(null)}/>}
    {records.map(use=><section key={use.id}><small>{new Date(use.created_at).toLocaleString('zh-CN')}</small>{use.failure_reason && <p role="alert">本次记忆未能提供：{use.failure_reason}</p>}{use.notice && <p>{use.notice}</p>}
      {(use.project_memories ?? []).map(item=><article key={item.id}><strong>{item.title}</strong> · v{item.revision} · 项目记忆<p>{item.content}</p><small>{item.source_ref}</small>{sourceId && projectId && item.editable && <button disabled={correctReference.isPending} onClick={()=>correctReference.mutate(item.id)}>纠正此条</button>}</article>)}
      {use.items.map(item=><article key={item.id}><strong>{item.title}</strong> · v{item.revision} · {item.scope==='shared'?'通用经验':'项目记忆'}<p>{item.content}</p>{sourceId && <button disabled={correct.isPending} onClick={()=>correct.mutate(item.id)}>纠正此条</button>}{item.applicability && <p>适用条件：{item.applicability}</p>}<details><summary>来源 · {item.evidence.length}</summary>{item.evidence.map(e=><p key={e.id}>{e.summary} · {experienceEvidenceLabels[e.verification]} · <MemorySource source={e.source_ref}/></p>)}</details>{item.truncated && <small>本条仅提供部分内容</small>}</article>)}{use.truncated && <small>本次上下文未包含全部内容</small>}</section>)}
  </details>;
}
