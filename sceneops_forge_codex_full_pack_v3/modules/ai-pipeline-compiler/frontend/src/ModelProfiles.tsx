import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { harness, harnessKeys, type Catalog, type ModelProfile } from './client';

export function ModelProfiles({catalog}:{catalog:Catalog}) {
  return <details><summary>运行时模型策略 · {catalog.model_provider} / {catalog.default_model}</summary><p>不同专家按能力层级路由。留空使用当前默认模型；保存不会调用模型，不会切换供应商。调整后需要重新生成计划。</p>{catalog.model_profiles.map(profile=><ProfileRow key={`${profile.provider}:${profile.tier}:${profile.model}`} profile={profile}/>)}</details>;
}
function ProfileRow({profile}:{profile:ModelProfile}) {
  const [model,setModel]=useState(profile.model??'');
  const cache=useQueryClient();
  const save=useMutation({mutationFn:()=>harness.saveProfile(profile.tier,model.trim()||null),onSuccess:()=>cache.invalidateQueries({queryKey:harnessKeys.catalog})});
  return <div className="harness-profile-row"><label>{profile.tier}<input value={model} onChange={e=>setModel(e.target.value)} placeholder="使用当前默认模型" disabled={save.isPending}/></label><button disabled={save.isPending} onClick={()=>save.mutate()}>保存策略</button>{save.error&&<p role="alert">{save.error.message}</p>}</div>;
}
