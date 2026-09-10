import {useState,type ReactNode} from 'react';
type AnimationRenderer=(input:{url:string;suspended:boolean})=>ReactNode;
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query';
import {agentTasks,agentTaskKeys,type AgentTask} from './client';
import type {components} from './generated/agent-api';
type Asset=components['schemas']['ProjectAssetEntry'];
type MaterialTarget={assetId:string;assetVersion:number};
export function ProjectAssetWorkbench({projectId,onOpenMaterial,renderAnimation,suspended=false}:{renderAnimation?:AnimationRenderer;suspended?:boolean;projectId:string;onOpenMaterial:(target:MaterialTarget)=>void}){
 const tasks=useQuery({queryKey:agentTaskKeys.list(projectId),queryFn:({signal})=>agentTasks.list(projectId,signal),refetchInterval:3000});
 const task=tasks.data?.tasks.find(item=>item.observations.native_production && !item.archived);
 const entities=useQuery({queryKey:['production-entities',task?.id],queryFn:()=>agentTasks.entities(task!.id),enabled:!!task,refetchInterval:3000});
 const content=useQuery({queryKey:agentTaskKeys.content(task?.id??''),queryFn:({signal})=>agentTasks.content(task!.id,signal),enabled:!!task,refetchInterval:3000});
 if(tasks.error||content.error||entities.error)return <p role="alert">项目资产读取失败：{(tasks.error||content.error||entities.error)?.message}</p>;
 if(!task)return null;
 return <section aria-label="当前游戏资产"><h3>当前游戏资产</h3><p>与场景、材质和游戏构建共用同一份资产记录。保存模型产生候选版本，应用引用后更新游戏。</p>{content.data?.assets.map(asset=><AssetEditor renderAnimation={renderAnimation} entities={entities.data??[]} suspended={suspended} key={asset.id} asset={asset} task={task} sceneVersion={content.data!.scene_version} instances={content.data!.instances} onOpenMaterial={onOpenMaterial}/>)}{content.data&&!content.data.assets.length&&<p>游戏尚未登记独立模型。源码几何需要先登记，才能在模型工具里编辑。</p>}</section>;
}
function AssetEditor({asset,task,sceneVersion,instances,onOpenMaterial,suspended,entities,renderAnimation}:{renderAnimation?:AnimationRenderer;entities:components['schemas']['ProductionEntity'][];suspended:boolean;asset:Asset;task:AgentTask;sceneVersion:number;instances:components['schemas']['DemoContentIndex']['instances'];onOpenMaterial:(target:MaterialTarget)=>void}){
 const [preview,setPreview]=useState(false);
 const cache=useQueryClient();const [selected,setSelected]=useState<number|null>(null);const version=selected??asset.current_version;
 const source=asset.versions.find(v=>v.source_version===version)!;
 const pending=Object.entries((task.observations.blender_candidates??{}) as Record<string,{asset_id:string;status:string}>).find(([,c])=>c.asset_id===asset.id&&['editing','exported'].includes(c.status));
 const refresh=()=>{void cache.invalidateQueries({queryKey:['agent-tasks']});void cache.invalidateQueries({queryKey:['project-assets']});void cache.invalidateQueries({queryKey:['production-entities']});void cache.invalidateQueries({queryKey:['environment-scene']});};
 const blender=useMutation({mutationFn:()=>agentTasks.blenderContent(task.id,{request_id:crypto.randomUUID(),operation:pending?'publish':'begin',candidate_id:pending?.[0],apply_to_scene:false,edits:[],target:{kind:'asset',id:asset.id,project_id:asset.project_id,workspace_id:asset.workspace_id!,source_version:version,expected_scene_version:sceneVersion}}),onSuccess:refresh});
 const rebind=useMutation({mutationFn:()=>agentTasks.saveContent(task.id,{asset_version:version,target:{kind:'asset',id:asset.id,project_id:asset.project_id,workspace_id:asset.workspace_id!,source_version:version,expected_scene_version:sceneVersion}}),onSuccess:refresh});
 const adopt=useMutation({mutationFn:(entity:components['schemas']['ProductionEntity'])=>agentTasks.adoptEntity(task.id,entity.id,{request_id:crypto.randomUUID(),expected_revision:entity.revision,asset_version:version}),onSuccess:refresh});
 const reconcile=useMutation({mutationFn:()=>agentTasks.blenderContent(task.id,{request_id:crypto.randomUUID(),operation:'reconcile',apply_to_scene:false,target:{kind:'asset',id:asset.id,project_id:asset.project_id,workspace_id:asset.workspace_id!,source_version:version,expected_scene_version:sceneVersion}}),onSuccess:refresh});
 const close=useMutation({mutationFn:()=>agentTasks.blenderContent(task.id,{request_id:crypto.randomUUID(),operation:'close_candidate',candidate_id:pending?.[0],apply_to_scene:false,target:{kind:'asset',id:asset.id,project_id:asset.project_id,workspace_id:asset.workspace_id!,source_version:version,expected_scene_version:sceneVersion}}),onSuccess:refresh});
 const evidence=blender.data?.actions.at(-1)?.result?.evidence;
 const notice=evidence&&typeof evidence==='object'&&!Array.isArray(evidence)?evidence.notice:undefined;
 const uncertain=task.actions.some(a=>['blender.asset.begin','blender.asset.edit','blender.asset.publish'].includes(a.action.capability_id)&&(a.state==='uncertain'||(a.state==='running'&&!a.run_ids?.length)));
 const busy=!!task.owner_pid||['running','queued','cancel_pending'].includes(task.status)||blender.isPending||rebind.isPending;
 const references=instances.filter(i=>i.asset_id===asset.id);
 return <article className="production-domain-package"><strong>{asset.title}</strong><p>模型 v{asset.current_version} · 场景引用 {references.map(i=>`v${i.asset_version}`).join('、')||'无'} · {source.blend_path?'已有 Blender 可编辑源':'尚无 Blender 源'}</p>
 {entities.filter(entity=>entity.asset_id===asset.id).map(entity=><p key={entity.id}>{entity.title}模板采用 v{entity.adopted_asset_version} <button disabled={busy||adopt.isPending||entity.adopted_asset_version===version} onClick={()=>adopt.mutate(entity)}>应用所选版本到模板</button></p>)}
 {renderAnimation&&<button onClick={()=>setPreview(!preview)}>{preview?'关闭动画预览':'查看实际模型与动画'}</button>}
 {preview&&renderAnimation?.({suspended,url:`/api/project-assets/${encodeURIComponent(asset.id)}/versions/${version}/files/preview?project_id=${encodeURIComponent(asset.project_id)}`})}
 <label>查看／采用版本 <select value={version} onChange={e=>setSelected(Number(e.target.value))}>{asset.versions.map(v=><option key={v.source_version} value={v.source_version}>v{v.source_version}</option>)}</select></label>
 {version!==asset.current_version&&!pending&&<p>历史版本可预览和重新采用；继续模型编辑请选择最新版本。</p>}
 {uncertain&&<p>上次模型编辑结果待核查。<button disabled={reconcile.isPending||!!task.owner_pid} onClick={()=>reconcile.mutate()}>读取 Blender 原请求结果</button></p>}
 <div className="production-domain-tools"><button disabled={busy||(!pending&&version!==asset.current_version)||!['glb','blender','procedural'].includes(source.source_kind)} onClick={()=>blender.mutate()}>{pending?'保存模型候选版本':'用 Blender 编辑（30 分钟编辑授权）'}</button><button onClick={()=>onOpenMaterial({assetId:asset.id,assetVersion:version})}>编辑此版本材质</button><button disabled={busy||!references.some(i=>i.asset_version!==version)} onClick={()=>rebind.mutate()}>应用到场景引用</button></div>
 {pending?.[1].status==='exported'&&<button disabled={busy||close.isPending} onClick={()=>close.mutate()}>结束此候选编辑（保留已导出文件）</button>}
 {typeof notice==='string'&&<p role="alert">{notice}</p>}
 {(blender.error||rebind.error||reconcile.error||close.error||adopt.error)&&<p role="alert">{(blender.error||rebind.error||reconcile.error||close.error||adopt.error)?.message}</p>}{blender.data?.actions.at(-1)?.state==='failed'&&<p role="alert">{blender.data.actions.at(-1)?.reason}</p>}
 </article>;
}
