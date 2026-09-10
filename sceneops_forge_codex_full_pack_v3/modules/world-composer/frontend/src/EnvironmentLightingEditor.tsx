import {useState} from 'react';
import {useMutation,useQueryClient} from '@tanstack/react-query';
import {environmentSceneClient,environmentSceneKey,type EnvironmentScene,type SceneLighting} from './environment-client';

export function EnvironmentLightingEditor({scene}:{scene:EnvironmentScene}) {
 const cache=useQueryClient();const [draft,setDraft]=useState<SceneLighting|null>(null);
 const value=draft??scene.lighting;
 const save=useMutation({mutationFn:()=>environmentSceneClient.saveLighting(scene.project_id,{expected_version:scene.version,lighting:value!}),onSuccess:next=>{cache.setQueryData(environmentSceneKey(scene.project_id),next);setDraft(null);}});
 if(!value)return <details><summary>游戏场景灯光</summary><p>当前工程灯光尚未登记。先由制作会话提取实际灯光；登记后在此编辑，重新构建应用。</p></details>;
 const update=(index:number,patch:Partial<NonNullable<SceneLighting['lights']>[number]>)=>setDraft({...value,lights:value.lights?.map((light,i)=>i===index?{...light,...patch}:light)});
 return <details><summary>游戏场景灯光 · {value.lights?.length??0} 盏</summary><p>与当前游戏共用场景版本。保存后更新游戏，已有运行窗口不做热替换。</p>
 <label>背景<input type="color" value={value.background} onChange={e=>setDraft({...value,background:e.target.value})}/></label>
 <label>曝光<input type="number" min="0.01" max="10" step="0.05" value={value.exposure} onChange={e=>setDraft({...value,exposure:Number(e.target.value)})}/></label>
 {value.lights?.map((light,index)=><fieldset key={light.id}><legend>{light.name}</legend><small>{light.id} · {light.type}</small>
 <label>启用<input type="checkbox" checked={light.enabled??true} onChange={e=>update(index,{enabled:e.target.checked})}/></label>
 <label>颜色<input type="color" value={light.color} onChange={e=>update(index,{color:e.target.value})}/></label>
 <label>强度<input type="number" min="0" step="0.1" value={light.intensity} onChange={e=>update(index,{intensity:Number(e.target.value)})}/></label>
 {light.type==='hemisphere'&&<label>地面反射色<input type="color" value={light.ground_color} onChange={e=>update(index,{ground_color:e.target.value})}/></label>}
 {light.type!=='ambient'&&light.type!=='hemisphere'&&(['position','target'] as const).map(key=><div key={key}>{key==='position'?'位置':'照向'}{[0,1,2].map(axis=><label key={axis}>{['X','Y','Z'][axis]}<input type="number" step="0.1" value={(light[key]??[0,0,0])[axis]} onChange={e=>{const vector=[...(light[key]??[0,0,0])] as [number,number,number];vector[axis]=Number(e.target.value);update(index,{[key]:vector});}}/></label>)}</div>)}
 </fieldset>)}
 <button disabled={!draft||save.isPending} onClick={()=>save.mutate()}>保存场景灯光，待更新游戏</button>{save.error&&<p role="alert">{save.error.message}</p>}
 </details>;
}
