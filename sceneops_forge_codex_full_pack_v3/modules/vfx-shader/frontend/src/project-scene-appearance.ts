import {Group,type Object3D} from 'three/webgpu';
import {requestJson} from '@sceneops/api-client';
import {createLookdevClient,type LookdevDocument} from './lookdev-client';
import {parseProject} from './core/lookdev';
import {loadGlbScene} from './core/three-lookdev';
import {buildRenderScene} from './core/render-scene';

/** Resolve saved appearance by exact project/asset/version; never execute stored module text. */
export async function loadProjectSceneAppearance(target:{projectId:string;assetId:string;assetVersion:number;instanceId:string;documentId?:string|null;documentVersion?:number|null}):Promise<Object3D>{
 const api=createLookdevClient(target.projectId);
 const bytes=await api.source({asset_id:target.assetId,asset_version:target.assetVersion,scene_instance_id:target.instanceId});
 const source=await loadGlbScene(bytes);
 const bindings=await api.bindings();
 const binding=bindings.find(item=>item.asset_id===target.assetId&&item.asset_version===target.assetVersion&&(!item.scene_instance_id||item.scene_instance_id===target.instanceId));
 const document= !binding&&target.documentId ? await requestJson<LookdevDocument>(`/api/lookdev/${encodeURIComponent(target.projectId)}/documents/${encodeURIComponent(target.documentId)}?version=${target.documentVersion}`):null;
 const state=binding?.state??document?.state;
 if(!state)return source;
 const project=parseProject(state);
 const editedLights=new Set(project.editLog.flatMap(entry=>entry.operations.flatMap(op=>op.kind==='light.add'?[op.light.id]:op.kind==='light.update'?[op.targetId]:[])));
 const render=buildRenderScene(source,{...project,lights:project.lights.filter(light=>light.sourceLightIndex!==undefined||editedLights.has(light.id))},null);
 const group=new Group();group.add(...[...render.scene.children]);
 return group;
}
