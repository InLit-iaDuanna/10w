import {useState} from 'react';
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {agentTasks,type AgentTask} from './client';
import type {components} from './generated/agent-api';
type Entity=components['schemas']['ProductionEntity'];
export type EntityMaterialTarget={entityDefinitionId:string;assetId:string;assetTitle:string;assetVersion:number;sceneVersion:number};
export function ProductionEntityPanel({task,featureId,onOpenMaterial}:{task:AgentTask;featureId:string;onOpenMaterial?:(target:EntityMaterialTarget)=>void}) {
  const entities=useQuery({queryKey:['production-entities',task.id],queryFn:()=>agentTasks.entities(task.id),refetchInterval:3000});
  const content=useQuery({queryKey:['agent-tasks',task.id,'content'],queryFn:()=>agentTasks.content(task.id),refetchInterval:3000});
  if(entities.error || content.error)return <p role="alert">对象读取失败：{(entities.error||content.error)?.message}</p>;
  return <section aria-label="关联生产对象">{entities.data?.filter(e=>e.feature_id===featureId).map(entity=>{
    const asset=content.data?.assets.find(a=>a.id===entity.asset_id);
    return asset && <EntityEditor key={entity.id} task={task} entity={entity} asset={asset} sceneVersion={content.data!.scene_version} onOpenMaterial={onOpenMaterial}/>;
  })}</section>;
}
function EntityEditor({task,entity,asset,sceneVersion,onOpenMaterial}:{task:AgentTask;entity:Entity;asset:components['schemas']['ProjectAssetEntry'];sceneVersion:number;onOpenMaterial?:(target:EntityMaterialTarget)=>void}) {
  const cache=useQueryClient();
  const [selected,setSelected]=useState<number|null>(null);
  const version=selected??asset.current_version;
  const candidate=Object.entries((task.observations.blender_candidates??{}) as Record<string,{asset_id:string;status:string}>).find(([,c])=>c.asset_id===asset.id&&['editing','exported'].includes(c.status));
  const refresh=()=>{void cache.invalidateQueries({queryKey:['agent-tasks']});void cache.invalidateQueries({queryKey:['production-entities']});};
  const adopt=useMutation({mutationFn:()=>agentTasks.adoptEntity(task.id,entity.id,{request_id:crypto.randomUUID(),expected_revision:entity.revision,asset_version:version}),onSuccess:refresh});
  const blender=useMutation({mutationFn:()=>agentTasks.blenderContent(task.id,{request_id:crypto.randomUUID(),operation:candidate?'publish':'begin',candidate_id:candidate?.[0],apply_to_scene:false,edits:[],target:{kind:'asset',id:asset.id,project_id:entity.project_id,workspace_id:entity.workspace_id,source_version:asset.current_version,expected_scene_version:sceneVersion}}),onSuccess:refresh});
  const busy=!!task.owner_pid||['running','queued','cancel_pending'].includes(task.status)||blender.isPending||adopt.isPending;
  return <article><h3>{entity.title}</h3><p>可复用对象模板 · 游戏采用 v{entity.adopted_asset_version} · 已保存至 v{asset.current_version}</p>
    <button disabled={busy} onClick={()=>blender.mutate()}>{candidate?'保存模型源与新版本':'用 Blender 编辑模型（30 分钟编辑授权）'}</button>
    <button disabled={busy||!onOpenMaterial} onClick={()=>onOpenMaterial?.({entityDefinitionId:entity.id,assetId:asset.id,assetTitle:asset.title,assetVersion:asset.current_version,sceneVersion})}>编辑材质</button>
    <label>采用版本 <select value={version} onChange={e=>setSelected(Number(e.target.value))}>{asset.versions.map(v=><option key={v.source_version} value={v.source_version}>v{v.source_version}{v.source_version===entity.adopted_asset_version?' · 当前采用':''}</option>)}</select></label>
    <button disabled={busy||version===entity.adopted_asset_version} onClick={()=>adopt.mutate()}>应用到对象模板</button>
    <p>保存保留候选；应用后更新游戏并重新试玩，后续生成的对象使用所选版本。</p>
    {(blender.error||adopt.error)&&<p role="alert">{(blender.error||adopt.error)?.message}</p>}
    {blender.data?.actions.at(-1)?.state==='failed'&&<p role="alert">{blender.data.actions.at(-1)?.reason}</p>}
  </article>;
}
