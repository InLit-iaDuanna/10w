import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentTasks, agentTaskKeys, type AgentTask } from './client';
import { productionKeys } from './production-client';

const SKILLS = [
  ['sceneops-threejs-gameplay','Gameplay 玩法'],['sceneops-threejs-graphics','Graphics 画面'],
  ['sceneops-threejs-ui','UI 交互'],['sceneops-threejs-debug','Debug 调试'],['sceneops-threejs-qa','QA 检查'],
] as const;
const DEFAULT_SKILLS = SKILLS.map(([id])=>id);

/** The reviewed brief and execution authorization are one explicit user action. */
export function CreationBriefPanel({task}: {task: AgentTask}) {
  const cache = useQueryClient();
  const [draft, setDraft] = useState<{content:string;version:number;selectedSkills:string[]} | null>(null);
  const query = useQuery({queryKey:agentTaskKeys.creationBrief(task.id),
    queryFn:({signal})=>agentTasks.creationBrief(task.id, signal), retry:false});
  const card = task.authorization_card;
  const confirm = useMutation({mutationFn:async()=>{
    if (!query.data) throw new Error('请先读取制作简报。');
    const content = draft?.content ?? query.data.content;
    const selectedSkills = draft?.selectedSkills ?? query.data.selected_skills ?? DEFAULT_SKILLS;
    const unchanged = content === query.data.content
      && selectedSkills.join('\n') === (query.data.selected_skills ?? DEFAULT_SKILLS).join('\n');
    const brief = unchanged ? query.data
      : await agentTasks.saveCreationBrief(task.id, {expected_version:draft?.version ?? query.data.version,
          content, selected_skills:selectedSkills as typeof query.data.selected_skills});
    cache.setQueryData(agentTaskKeys.creationBrief(task.id), brief);
    setDraft({content:brief.content,version:brief.version,selectedSkills:brief.selected_skills ?? DEFAULT_SKILLS});
    await agentTasks.authorize(task.id, {authorization_card_id:card.id, accept_unknown_cost:true,
      accept_full_access:card.permission_mode === 'full', creation_brief_version:brief.version});
  }, onSettled:async()=>{
    await cache.invalidateQueries({queryKey:['agent-tasks']});
    await cache.invalidateQueries({queryKey:productionKeys.snapshot(task.project_id)});
  }});
  const cancel = useMutation({mutationFn:()=>agentTasks.cancel(task.id), onSuccess:async()=>{
    await cache.invalidateQueries({queryKey:['agent-tasks']});
    await cache.invalidateQueries({queryKey:productionKeys.snapshot(task.project_id)});
  }});
  const pending = confirm.isPending || cancel.isPending;
  return <section className="agent-authorization" aria-label="制作简报与执行确认">
    <header><strong>确认制作简报</strong><span>版本 {query.data?.version ?? '…'}</span></header>
    <p>核对目标、必做内容和边界；可直接修改。确认后开始原生制作，后续要求沿用同一会话。</p>
    {query.isPending && <p role="status">正在读取制作简报…</p>}
    {query.error && <p role="alert">{query.error.message}<button onClick={()=>void query.refetch()}>重新读取</button></p>}
    {query.data && <textarea aria-label="制作简报" rows={16} maxLength={128000}
      style={{width:'100%',boxSizing:'border-box'}} value={draft?.content ?? query.data.content}
      disabled={pending} onChange={event=>setDraft({content:event.target.value,version:draft?.version ?? query.data!.version,
        selectedSkills:draft?.selectedSkills ?? query.data!.selected_skills ?? DEFAULT_SKILLS})} />}
    {query.data && <fieldset disabled={pending}><legend>本次原生制作加载的 Skills</legend>
      <p>由你决定把哪些 SceneOps 技能放入 Codex / CodeBuddy harness；没有选中的不会被加载。</p>
      {SKILLS.map(([id,label]) => {
        const selected = draft?.selectedSkills ?? query.data!.selected_skills ?? DEFAULT_SKILLS;
        return <label key={id}><input type="checkbox" checked={selected.includes(id)} onChange={event=>{
          const next = event.target.checked ? [...selected,id] : selected.filter(item=>item!==id);
          setDraft({content:draft?.content ?? query.data!.content,version:draft?.version ?? query.data!.version,selectedSkills:next});
        }}/>{label}</label>;
      })}
    </fieldset>}
    <p>执行器：{task.provider_id === 'codebuddycli' ? 'CodeBuddy' : 'Codex'} · 模型：{task.provider_model ?? 'CLI 默认模型'}</p>
    <p>流程：原生 Plan 对齐简报与游戏架构 → 同一 harness 直接制作 → 返回工作台试玩。</p>
    <p>权限：{card.permission_mode === 'full' ? '完整权限' : '当前任务范围'} · 工作区：<code>{card.workspace_root}</code></p>
    <details><summary>查看执行范围</summary><p>{card.scope}</p><p>{card.cost_notice}</p></details>
    <div className="agent-authorization-actions">
      <button disabled={!query.data || !(draft?.content ?? query.data?.content ?? '').trim() || pending}
        onClick={()=>confirm.mutate()}>{confirm.isPending ? '正在保存并开始…' : '确认简报并开始制作'}</button>
      <button disabled={pending} onClick={()=>cancel.mutate()}>返回讨论</button>
    </div>
    {confirm.error && <p role="alert">{confirm.error.message} 当前草稿已保留。</p>}
    {cancel.error && <p role="alert">{cancel.error.message}</p>}
  </section>;
}
