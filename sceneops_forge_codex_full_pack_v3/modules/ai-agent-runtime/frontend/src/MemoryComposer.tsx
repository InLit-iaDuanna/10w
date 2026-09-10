import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { experienceApi, type MemoryWrite } from './experience-client';
export function MemoryComposer({value,onClose}:{value:MemoryWrite;onClose:()=>void}) {
  const [draft,setDraft]=useState<MemoryWrite>(()=>({...value,request_id:crypto.randomUUID()})); const cache=useQueryClient(); const [notice,setNotice]=useState('');
  const save=useMutation({mutationFn:()=>experienceApi.remember(draft),onSuccess:event=>{void cache.invalidateQueries({queryKey:['experience']});if(!event.persisted || event.state==='failed'){setNotice(event.reason || '记忆未保存，请重试。');return;}onClose();}});
  return <form className="experience-editor memory-composer" onSubmit={event=>{event.preventDefault();setNotice('');save.mutate();}}>
    <label>标题<input disabled={save.isPending} required maxLength={240} value={draft.title} onChange={event=>setDraft({...draft,request_id:crypto.randomUUID(),title:event.target.value})}/></label>
    <label>分类<select disabled={save.isPending} value={draft.category ?? 'fact'} onChange={event=>setDraft({...draft,request_id:crypto.randomUUID(),category:event.target.value as MemoryWrite['category']})}><option value="decision">已确认决定</option><option value="constraint">执行约束</option><option value="fact">项目事实</option></select></label>
    <label>记住的内容<textarea disabled={save.isPending} required rows={4} maxLength={16000} value={draft.content} onChange={event=>setDraft({...draft,request_id:crypto.randomUUID(),content:event.target.value})}/></label>
    <small>保存后对后续任务生效，正在进行的任务保留原有依据。</small>
    {notice && <p role="alert">未保存，编辑内容已保留：{notice}</p>}{save.error && <p role="alert">未保存，编辑内容已保留：{save.error.message}</p>}
    <div className="experience-editor-actions"><button disabled={save.isPending}>{save.isPending?'保存中…':'保存记忆'}</button><button type="button" disabled={save.isPending} onClick={onClose}>取消</button></div>
  </form>;
}
