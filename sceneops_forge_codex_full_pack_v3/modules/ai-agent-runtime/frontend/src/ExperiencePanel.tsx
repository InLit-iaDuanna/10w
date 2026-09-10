import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { SourceIcon } from './SourceIcon';
import { experienceApi } from './experience-client';
import { MemoryLibrary } from './MemoryLibrary';
import { ExperienceLibrary } from './ExperienceLibrary';
import { ExperienceSettings } from './ExperienceSettings';
import './experience.css';
const batchLabels: Record<string,string> = {pending:'等待学习',running:'学习中',completed:'已完成',failed:'失败',budget_wait:'等待预算',paused:'已暂停',interrupted:'已中断'};
export function ExperiencePanel({projectId}: {projectId:string|null}) {
  const [open,setOpen]=useState(false); const [loaded,setLoaded]=useState(false); const trigger=useRef<HTMLButtonElement>(null);
  useEffect(()=>{if(loaded && !open) trigger.current?.focus();},[loaded,open]);
  return <div className="experience-launcher"><button ref={trigger} type="button" title="查看经验" aria-label="经验" aria-haspopup="dialog" aria-expanded={open} onClick={()=>{setLoaded(true);setOpen(true);}}><SourceIcon name="file"/><span>经验</span></button>{loaded && createPortal(<ExperienceDialog key={projectId ?? 'global'} projectId={projectId} open={open} onClose={()=>setOpen(false)}/>,document.body)}</div>;
}
function ExperienceDialog({projectId,open,onClose}: {projectId:string|null;open:boolean;onClose:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null); const [tab,setTab]=useState(projectId?'memory':'library'); const cache=useQueryClient();
  useEffect(()=>{if(open) dialog.current?.showModal();else if(dialog.current?.open) dialog.current.close();},[open]);
  const status=useQuery({queryKey:['experience','status'],queryFn:experienceApi.status,retry:false,enabled:open,refetchInterval:open?5000:false});
  const learn=useMutation({mutationFn:()=>experienceApi.learn(projectId),onSuccess:()=>void cache.invalidateQueries({queryKey:['experience']})});
  return <dialog ref={dialog} className="experience-dialog" aria-label="经验" onCancel={event=>{event.preventDefault();onClose();}}>
    <header className="experience-header"><div className="experience-brand"><span className="experience-brand-mark"><SourceIcon name="file"/></span><div><h2>经验</h2><p>把解决过的问题，留给下一次工作。</p></div></div><div className="experience-header-right"><button type="button" id="experience-tab-settings" aria-pressed={tab==='settings'} onClick={()=>setTab('settings')}>设置</button><span className="experience-live-state">{status.data ? status.data.settings.learn_enabled?'自动学习已开启':'自动学习已暂停':'正在连接'}</span><button type="button" onClick={onClose} aria-label="关闭经验" title="返回对话"><SourceIcon name="close"/></button></div></header>
    <div className="experience-tabs" role="tablist" aria-label="经验视图">{[['memory','项目记忆'],['library','通用经验'],['activity','学习动态']].map(([id,label])=><button key={id} role="tab" type="button" id={`experience-tab-${id}`} aria-selected={tab===id} aria-controls={`experience-view-${id}`} onClick={()=>setTab(id)}>{label}{id==='activity' && !!status.data?.pending_sources && <span>{status.data.pending_sources}</span>}</button>)}</div>
    {status.error && <p className="experience-notice" role="alert">连接失败：{status.error.message} <button onClick={()=>void status.refetch()}>重试</button></p>}
    <section role="tabpanel" id="experience-view-memory" aria-labelledby="experience-tab-memory" hidden={tab!=='memory'} className="experience-library-panel"><MemoryLibrary projectId={projectId} open={open && tab==='memory'}/></section>
    <section role="tabpanel" id="experience-view-library" aria-labelledby="experience-tab-library" hidden={tab!=='library'} className="experience-library-panel"><ExperienceLibrary projectId={projectId} open={open && tab==='library'} sharedOnly/></section>
    <section role="tabpanel" id="experience-view-activity" aria-labelledby="experience-tab-activity" hidden={tab!=='activity'} className="experience-page">
      <div className="experience-page-heading"><div><h3>学习动态</h3><p>查看学习进度与真实调用记录。</p></div><button className="experience-primary" disabled={learn.isPending || !status.data?.settings.learn_enabled} onClick={()=>learn.mutate()}><SourceIcon name="refresh"/>{learn.isPending?'正在学习…':'学习待处理记录'}</button></div>
      {status.isPending && <p role="status">读取学习记录…</p>}{status.data && <><div className="experience-metrics"><div><small>待学习来源</small><strong>{status.data.pending_sources}</strong></div><div><small>今日调用</small><strong>{status.data.calls_used}<span> / {status.data.settings.daily_call_limit}</span></strong></div><div><small>今日费用</small><strong>{status.data.cost_usd == null?'未知':`$${status.data.cost_usd.toFixed(4)}`}</strong></div></div>
      {status.data.last_error && <p role="alert">{status.data.last_error}</p>}
      <div className="experience-batches">{status.data.batches.length===0?<div className="experience-empty"><SourceIcon name="refresh"/><h3>还没有学习记录</h3><p>新对话与执行记录会在开启学习后逐步整理。</p></div>:status.data.batches.map(batch=><article key={batch.id}><div><strong>{batchLabels[batch.status]}</strong><time>{new Date(batch.created_at).toLocaleString('zh-CN')}</time></div><p>{batch.reason || '无补充原因'}</p><small>{batch.calls} 次调用 · {batch.provider ?? '未调用'} / {batch.model ?? '未记录模型'}</small></article>)}</div></>}
      {learn.error && <p role="alert">学习失败：{learn.error.message}</p>}
    </section>
    <section role="tabpanel" id="experience-view-settings" aria-labelledby="experience-tab-settings" hidden={tab!=='settings'} className="experience-page">{status.data?<ExperienceSettings settings={status.data.settings}/>:<p role="status">读取设置…</p>}</section>
  </dialog>;
}
