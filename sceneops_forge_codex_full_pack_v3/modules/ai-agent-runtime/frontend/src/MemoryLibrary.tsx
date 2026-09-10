import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { experienceApi } from './experience-client';
import { ExperienceDetail, type EntryDraft } from './ExperienceDetail';
const categories=[['decision','已确认决定'],['constraint','执行约束'],['fact','项目事实']] as const;
export function MemoryLibrary({projectId,open}:{projectId:string|null;open:boolean}) {
  const [search,setSearch]=useState(''); const [selected,setSelected]=useState<string|null>(null); const [drafts,setDrafts]=useState<Record<string,EntryDraft>>({});
  const query=useQuery({queryKey:['experience','project-memory',projectId],queryFn:()=>experienceApi.projectMemory(projectId!),enabled:open && !!projectId,retry:false});
  if(!projectId) return <div className="experience-empty"><h3>选择项目后查看项目记忆</h3><p>通用经验可在不同项目中复用。</p></div>;
  if(selected) return <ExperienceDetail projectId={projectId} id={selected} topics={[]} draft={drafts[selected]} onDraft={draft=>setDrafts(value=>({...value,[selected]:draft}))} onBack={()=>setSelected(null)}/>;
  const matches=(item:{title:string;content:string})=>`${item.title} ${item.content}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase());
  return <div className="experience-page memory-library"><div className="experience-page-heading"><div><h3>项目记忆</h3><p>已确认的方向、执行约束和项目事实，随下一次任务一起读取。</p></div></div><input aria-label="搜索项目记忆" placeholder="搜索项目记忆…" value={search} onChange={event=>setSearch(event.target.value)}/>
    {query.isPending && <p role="status">读取项目记忆…</p>}{query.error && <p role="alert">读取失败：{query.error.message}<button onClick={()=>void query.refetch()}>重试</button></p>}
    {categories.map(([id,label])=><section key={id}><h4>{label}</h4>{query.data?.references.filter(item=>item.category===id && matches(item)).map(item=><details className="experience-references" key={item.id}><summary>{item.title} · v{item.revision}</summary><p>{item.content}</p><small>项目原始记录 · {item.source_ref}</small><p className="experience-muted">在对话中纠正这项决定，保存后会同步到这里。</p></details>)}{query.data?.entries.filter(item=>(item.memory_category ?? 'fact')===id && matches(item)).map(item=><button className="experience-entry" key={item.id} onClick={()=>setSelected(item.id)}><strong>{item.title}</strong><p>{item.content}</p><small>v{item.revision}{!item.enabled?' · 已停用':''}</small></button>)}</section>)}
    {query.data && !query.data.references.length && !query.data.entries.length && <p>还没有项目记忆。可以在对话消息下点击“记住”，或在讨论中明确确认决定。</p>}
  </div>;
}
