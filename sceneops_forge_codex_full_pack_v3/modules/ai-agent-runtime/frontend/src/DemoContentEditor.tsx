import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { agentTasks, agentTaskKeys, type AgentTask } from './client';
import type { components } from './generated/agent-api';
type Content=components['schemas']['DemoContentIndex'];
type Target=components['schemas']['DemoEditTarget'];
type Save=components['schemas']['DemoContentSave'];
type Entry={target:Target; title:string; mode:string; values:Record<string,string>; save:Save; source?:string; impact?:string[]};
export function demoEntries(content:Content, viewedCandidateId:string|null):Entry[] {
  const target=(kind:Target['kind'],id:string,version:number):Target=>({project_id:content.project_id,workspace_id:content.workspace_id,kind,id,source_version:version,viewed_candidate_id:viewedCandidateId,...(kind==='asset'?{expected_scene_version:content.scene_version}:{})});
  return [
    ...content.assets.map((asset):Entry=>{
      const recipe=asset.versions.find(v=>v.source_version===asset.current_version)?.recipe;
      const t=target('asset',asset.id,asset.current_version);
      return {target:t,title:asset.title,mode:recipe?'共享配方':'暂不支持属性编辑',values:recipe?{width_m:String(recipe.width_m),height_m:String(recipe.height_m),thickness_m:String(recipe.thickness_m),...(recipe.material?{color_hex:recipe.material.color_hex,roughness:String(recipe.material.roughness),metalness:String(recipe.material.metalness)}:{})}:{},save:{target:t,recipe},impact:content.instances.filter(i=>i.asset_id===asset.id).map(i=>`${i.title} (${i.id})`)};
    }),
    ...content.instances.flatMap(instance=>{
      const t=target('instance',instance.id,content.scene_version), transform=instance.transform;
      const entries:Entry[]=[{target:t,title:`${instance.title} · ${instance.id}`,mode:`实例属性 · 源资产 ${instance.asset_id}`,values:{x:String(transform.position_m?.[0]??0),y:String(transform.position_m?.[1]??0),z:String(transform.position_m?.[2]??0),rotation_y_deg:String(transform.rotation_y_deg),scale:String(transform.scale)},save:{target:t,transform}}];
      if(instance.behavior){const b=instance.behavior,bt=target('behavior',b.behavior_instance_id,content.scene_version);entries.push({target:bt,title:`${instance.title} · ${instance.id} · KeyDoor`,mode:'已有行为参数',values:{interaction_distance_m:String(b.interaction_distance_m),open_angle_deg:String(b.open_angle_deg),required_key_asset_id:b.required_key_asset_id},save:{target:bt}});}
      return entries;
    }),
    ...content.sources.map(source=>{const t={...target('source',source.id,source.source_version),expected_source_content:source.content};return {target:t,title:source.path,mode:'源码 / Agent',values:{},save:{target:t},source:source.content};}),
  ];
}
export function DemoContentEditor({task,content,viewedCandidateId,unavailable,agentUnavailable}:{task:AgentTask;content:Content;viewedCandidateId:string|null;unavailable:boolean;agentUnavailable:boolean}) {
  const entries=demoEntries(content,viewedCandidateId);
  const [selected,setSelected]=useState('');
  const entry=entries.find(item=>`${item.target.kind}:${item.target.id}`===selected);
  return <section aria-label="作品内容"><h3>继续修改</h3><p>{content.source_notice}</p>
    <label>选择实际内容<select value={selected} onChange={e=>setSelected(e.target.value)}><option value="">选择资产、实例、行为或源码</option>
      {(['asset','instance','behavior','source'] as const).map((kind,index)=><optgroup key={kind} label={['共享资产','场景实例','KeyDoor 行为','项目源码'][index]}>{entries.filter(e=>e.target.kind===kind).map(e=><option key={e.target.id} value={`${kind}:${e.target.id}`}>{e.title} · {e.mode}</option>)}</optgroup>)}</select></label>
    {!entries.length && <p>当前尚无已登记内容；制作进度见任务详情。</p>}
    {entry && <TargetEditor key={`${content.project_id}:${content.workspace_id}:${selected}`} entry={entry} task={task} unavailable={unavailable} agentUnavailable={agentUnavailable} />}
  </section>;
}
type Draft={version:number;values:Record<string,string>;goal:string;requestId:string|null;expectedSource?:string;expectedSceneVersion?:number};
const labels:Record<string,string>={color_hex:'材质颜色（HEX）',roughness:'粗糙度（0–1）',metalness:'金属度（0–1）',width_m:'宽度（米）',height_m:'高度（米）',thickness_m:'厚度（米）',x:'位置 X（米）',y:'位置 Y（米）',z:'位置 Z（米）',rotation_y_deg:'Y 轴旋转（度）',scale:'缩放',interaction_distance_m:'交互距离（米）',open_angle_deg:'开门角度（度）',required_key_asset_id:'所需钥匙资产 ID'};
const parameterBounds:Record<string,{min:number;max:number}>={width_m:{min:.2,max:10},height_m:{min:.5,max:10},thickness_m:{min:.02,max:2},roughness:{min:0,max:1},metalness:{min:0,max:1}};
function TargetEditor({entry,task,unavailable,agentUnavailable}:{entry:Entry;task:AgentTask;unavailable:boolean;agentUnavailable:boolean}) {
  const cache=useQueryClient();
  const key=`sceneops:demo-draft:${entry.target.project_id}:${entry.target.workspace_id}:${entry.target.kind}:${entry.target.id}`;
  const fresh=():Draft=>({version:entry.target.source_version,values:entry.values,goal:'',requestId:null,...(entry.target.expected_scene_version==null?{}:{expectedSceneVersion:entry.target.expected_scene_version}),...(entry.source===undefined?{}:{expectedSource:entry.source})});
  const [storageError,setStorageError]=useState('');
  const [draft,setDraft]=useState<Draft>(()=>{const stored=localStorage.getItem(key);if(!stored)return fresh();try{const saved=JSON.parse(stored) as Draft;return {...saved,values:{...entry.values,...saved.values}};}catch{return fresh();}});
  const change=(next:Draft)=>{setDraft(next);try{localStorage.setItem(key,JSON.stringify(next));setStorageError('');}catch{setStorageError('草稿无法存入浏览器；本页输入仍保留。');}};
  const target={...entry.target,source_version:draft.version,...(entry.target.kind==='asset'?{expected_scene_version:draft.expectedSceneVersion??null}:{}),...(draft.expectedSource===undefined?{}:{expected_source_content:draft.expectedSource})};
  const save=useMutation({mutationFn:()=>{
    const v=draft.values;const body:Save={target};
    if(entry.save.recipe)body.recipe={...entry.save.recipe,width_m:Number(v.width_m),height_m:Number(v.height_m),thickness_m:Number(v.thickness_m),...(entry.save.recipe.material?{material:{...entry.save.recipe.material,color_hex:v.color_hex!,roughness:Number(v.roughness),metalness:Number(v.metalness)}}:{})};
    if(entry.save.transform)body.transform={position_m:[Number(v.x),Number(v.y),Number(v.z)],rotation_y_deg:Number(v.rotation_y_deg),scale:Number(v.scale)};
    if(target.kind==='behavior'){body.interaction_distance_m=Number(v.interaction_distance_m);body.open_angle_deg=Number(v.open_angle_deg);body.required_key_asset_id=v.required_key_asset_id;}
    return agentTasks.saveContent(task.id,body);
  },onSuccess:result=>{cache.setQueryData(agentTaskKeys.content(task.id),result.content);const updated=demoEntries(result.content,entry.target.viewed_candidate_id??null).find(e=>e.target.kind===target.kind&&e.target.id===target.id);if(updated)change({...draft,version:updated.target.source_version,values:updated.values,...(updated.target.expected_scene_version==null?{}:{expectedSceneVersion:updated.target.expected_scene_version})});},onSettled:()=>cache.invalidateQueries({queryKey:agentTaskKeys.content(task.id)})});
  const followup=useMutation({mutationFn:()=>{const requestId=draft.requestId??crypto.randomUUID();change({...draft,requestId});return agentTasks.continueProjectDemo(task.id,{request_id:requestId,goal:draft.goal,target});},onSuccess:()=>{change({...draft,goal:'',requestId:null});void cache.invalidateQueries({queryKey:['agent-tasks']});}});
  const reload=useMutation({mutationFn:()=>agentTasks.content(task.id),onSuccess:result=>{cache.setQueryData(agentTaskKeys.content(task.id),result);const latest=demoEntries(result,entry.target.viewed_candidate_id??null).find(e=>e.target.kind===target.kind&&e.target.id===target.id);if(latest)change({...draft,version:latest.target.source_version,values:latest.values,...(latest.target.expected_scene_version==null?{}:{expectedSceneVersion:latest.target.expected_scene_version}),...(latest.source===undefined?{}:{expectedSource:latest.source})});}});
  const stale=draft.version!==entry.target.source_version || (entry.target.kind==='asset' && draft.expectedSceneVersion!==entry.target.expected_scene_version) || (entry.source!==undefined && draft.expectedSource!==entry.source);
  return <div className="demo-target-editor"><strong>{entry.title}</strong><p>{entry.mode} · 编辑源 v{entry.target.source_version} · 草稿基于 v{draft.version}</p>
    {entry.impact && <p>影响当前引用实例：{entry.impact.length?entry.impact.join('、'):'暂无引用实例'}</p>}
    {entry.source!==undefined && <><p>此源码通过 Agent 修改；当前没有通用参数面板。来源为已登记写入记录。</p><pre>{entry.source}</pre></>}
    {stale && <p role="alert">源已变更。草稿保留，请重新读取当前参数再保存。</p>}
    {Object.keys(draft.values).length>0 && <form onSubmit={e=>{e.preventDefault();save.mutate();}}><div className="demo-fields">{Object.entries(draft.values).map(([name,value])=><label key={name}>{labels[name]??name}<input disabled={save.isPending} required type={name==='required_key_asset_id'?'text':name==='color_hex'?'color':'number'} {...parameterBounds[name]} step="any" value={value} onChange={e=>change({...draft,values:{...draft.values,[name]:e.target.value}})} /></label>)}</div><button disabled={unavailable||stale||save.isPending}>保存源内容</button></form>}
    <button disabled={reload.isPending} onClick={()=>reload.mutate()}>重读当前参数（替换属性草稿）</button>
    {reload.error && <p role="alert">重读失败：{reload.error.message}。草稿保留。</p>}
    {save.error && <p role="alert">源保存失败：{save.error.message}。输入已保留。</p>}{save.data && <p role="status">{save.data.notice}</p>}
    <form onSubmit={e=>{e.preventDefault();followup.mutate();}}><label>让 Agent 修改此内容<textarea disabled={followup.isPending} rows={3} value={draft.goal} onChange={e=>change({...draft,goal:e.target.value,requestId:null})} /></label><button disabled={agentUnavailable||followup.isPending||!draft.goal.trim()||stale}>发送修改要求</button></form>
    {followup.error && <p role="alert">Agent 续改受阻：{followup.error.message}。目标、输入和重试编号已保留。</p>}{storageError && <p role="alert">{storageError}</p>}
  </div>;
}
