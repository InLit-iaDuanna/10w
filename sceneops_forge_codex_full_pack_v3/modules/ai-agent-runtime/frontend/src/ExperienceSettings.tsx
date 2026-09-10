import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { experienceApi, type ExperienceSettings as Settings } from './experience-client';
export function ExperienceSettings({settings}: {settings:Settings}) {
  const cache=useQueryClient(); const [draft,setDraft]=useState<Pick<Settings,'use_enabled'|'learn_enabled'|'batch_call_limit'|'daily_call_limit'>>({use_enabled:settings.use_enabled,learn_enabled:settings.learn_enabled,batch_call_limit:settings.batch_call_limit,daily_call_limit:settings.daily_call_limit});
  const save=useMutation({mutationFn:()=>experienceApi.settings(draft),onSuccess:()=>void cache.invalidateQueries({queryKey:['experience','status']})});
  return <form className="experience-settings" onSubmit={e=>{e.preventDefault();save.mutate();}}><div className="experience-page-heading"><div><h3>使用与学习</h3><p>决定何时提供经验，以及学习可使用的调用额度。</p></div></div>
    <label className="experience-setting-row"><span><strong>使用经验</strong><small>将相关经验提供给模型；不会扩大任务权限。</small></span><input role="switch" type="checkbox" checked={draft.use_enabled} onChange={e=>setDraft({...draft,use_enabled:e.target.checked})}/></label>
    <label className="experience-setting-row"><span><strong>自动学习</strong><small>从新的对话和执行记录中整理可复用的经验。</small></span><input role="switch" type="checkbox" checked={draft.learn_enabled} onChange={e=>setDraft({...draft,learn_enabled:e.target.checked})}/></label>
    <h4>调用额度</h4><label className="experience-setting-row"><span><strong>每批调用上限</strong><small>每个学习批次最多使用 2 次模型调用。</small></span><input aria-label="每批调用上限" type="number" min="1" max="2" required value={draft.batch_call_limit} onChange={e=>setDraft({...draft,batch_call_limit:Number(e.target.value)})}/></label><label className="experience-setting-row"><span><strong>每日调用上限</strong><small>按北京时间统计；达到上限后等待下一日。</small></span><input aria-label="每日调用上限" type="number" min="1" required value={draft.daily_call_limit} onChange={e=>setDraft({...draft,daily_call_limit:Number(e.target.value)})}/></label>
    <footer><button className="experience-primary" disabled={save.isPending}>{save.isPending?'保存中…':'保存设置'}</button>{save.isSuccess && <span role="status">设置已保存</span>}</footer>{save.error && <p role="alert">保存失败，修改仍保留：{save.error.message}</p>}
  </form>;
}
