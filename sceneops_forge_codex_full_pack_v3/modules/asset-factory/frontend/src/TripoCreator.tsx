import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CardModelPreview } from './CardModelPreview';
import { requestJson } from '@sceneops/api-client';
import { cardAssetClient, cardAssetKey } from './cardAssetClient';
import type { components } from './generated/card-assets-api';
import './tripo-creator.css';
type Settings=components['schemas']['TripoSettings'];
type Job=components['schemas']['TripoJob'];
const root='/api/card-assets';
const statusNames:Record<string,string>={submitting:'正在提交',submission_unknown:'提交结果待确认',queued:'排队中',running:'生成中',success:'生成成功',collected:'模型已下载',imported:'已加入模型工作流',failed:'生成失败',banned:'内容被拒绝',expired:'任务已过期',cancelled:'已取消',unknown:'状态不明'};
export function TripoCreator({projectId,cardId,sessionId,initialPrompt,onReady}:{projectId:string;cardId:string;sessionId:string;initialPrompt:string;onReady:()=>void}){
 const cache=useQueryClient();const settings=useQuery({queryKey:['tripo-settings'],queryFn:()=>requestJson<Settings>(root+'/tripo/settings'),retry:false});
 const jobsKey=['tripo-jobs',projectId,cardId,sessionId];
 const jobs=useQuery({queryKey:jobsKey,queryFn:()=>requestJson<Job[]>(`${root}/tripo/jobs?project_id=${encodeURIComponent(projectId)}&card_id=${encodeURIComponent(cardId)}&session_id=${encodeURIComponent(sessionId)}`),retry:false});
 const [secret,setSecret]=useState(''),[version,setVersion]=useState(''),[prompt,setPrompt]=useState(initialPrompt);
 const [input,setInput]=useState<'text'|'image'>('text'),[file,setFile]=useState<File|null>(null),[notice,setNotice]=useState('');
 const [selectedId,setSelectedId]=useState<string|null>(null);const requestId=useRef(crypto.randomUUID());const reference=useRef<{file:File;id:string}|null>(null);
 const current=selectedId??jobs.data?.[0]?.id;
 const job=useQuery({queryKey:['tripo-job',current],queryFn:()=>requestJson<Job>(`${root}/tripo/jobs/${current}`),enabled:!!current,retry:false,
  refetchInterval:query=>['queued','running'].includes(query.state.data?.status??'')?3000:false});
 const save=useMutation({mutationFn:()=>requestJson<Settings>(root+'/tripo/settings',{body:{model_version:version||settings.data?.model_version,...(secret?{api_key:secret}:{})}}),
  onSuccess:()=>{setSecret('');setNotice('Tripo 配置已保存在本机服务端。');void cache.invalidateQueries({queryKey:['tripo-settings']});}});
 const submit=useMutation({mutationFn:async()=>{
  let reference_id:string|undefined;
  if(input==='image'){
   if(!file)throw new Error('请选择参考图。');
   if(file.size>10*1024*1024)throw new Error('参考图不能超过 10 MiB。');
   if(reference.current?.file===file)reference_id=reference.current.id;
   else{const value=await cardAssetClient.reference(projectId,cardId,file);reference_id=value.id;reference.current={file,id:value.id};}
  }
  return requestJson<Job>(`${root}/${encodeURIComponent(projectId)}/${encodeURIComponent(cardId)}/tripo/jobs`,{body:{request_id:requestId.current,session_id:sessionId,prompt:input==='text'?prompt:'',...(reference_id?{reference_id}:{})},timeoutMs:150000});
 },onSuccess:result=>{setSelectedId(result.id);cache.setQueryData(['tripo-job',result.id],result);void cache.invalidateQueries({queryKey:jobsKey});},onError:()=>{void cache.invalidateQueries({queryKey:jobsKey});}});
 const collect=useMutation({mutationFn:(jobId:string)=>requestJson<Job>(`${root}/tripo/jobs/${jobId}/collect`,{body:{},timeoutMs:150000}),onSuccess:result=>cache.setQueryData(['tripo-job',result.id],result)});
 useEffect(()=>{if(job.data?.status==='success'&&!collect.isPending&&!collect.isError&&current)collect.mutate(current);},[job.data?.status,current,collect.isPending,collect.isError]);
 const imported=useMutation({mutationFn:(jobId:string)=>requestJson(`${root}/tripo/jobs/${jobId}/import`,{body:{},timeoutMs:610000}),onSuccess:async(_result,jobId)=>{
  await cache.invalidateQueries({queryKey:cardAssetKey(projectId,cardId)});await cache.invalidateQueries({queryKey:['tripo-job',jobId]});setNotice('模型已导入当前卡片，可继续检查并存入资产库。');onReady();}});
 const active=submit.isPending||!!job.data&&['queued','running','submitting','submission_unknown'].includes(job.data.status);
 return <section className="tripo-creator" aria-label="Tripo 模型生成">
  <header><div><h3>Tripo · AI 3D 生成</h3><p>文字或参考图 → 三维模型 → 当前项目</p></div><a href="https://platform.tripo3d.ai" target="_blank" rel="noreferrer">Tripo 控制台 ↗</a></header>
  <details open={!settings.data?.configured} className="tripo-settings"><summary>渠道设置 · {settings.data?.configured?'已配置':'未配置'}</summary>
   <label>API Key<input type="password" autoComplete="new-password" value={secret} placeholder={settings.data?.configured?'已保存；填写可更换':'输入 Tripo API Key'} onChange={event=>setSecret(event.target.value)}/></label>
   <label>生成模型<select value={version||settings.data?.model_version||''} onChange={event=>setVersion(event.target.value)}>{settings.data?.available_models?.map(item=><option key={item}>{item}</option>)}</select></label>
   <button disabled={save.isPending||!settings.data||(!settings.data.configured&&!secret)} onClick={()=>save.mutate()}>{save.isPending?'保存中…':'保存配置'}</button><small>密钥不回显、不写入项目文件；提交不会自动重试。</small>
  </details>
  <div className="tripo-input-tabs"><button aria-pressed={input==='text'} disabled={active} onClick={()=>setInput('text')}>文字生成</button><button aria-pressed={input==='image'} disabled={active} onClick={()=>setInput('image')}>图片生成</button></div>
  {input==='text'?<div><label>模型描述<textarea aria-label="模型描述" value={prompt} maxLength={1024} disabled={active} onChange={event=>setPrompt(event.target.value)} placeholder="例如：一位戴黄色安全帽的低多边形工程师，全身，正面站姿"/><small>{prompt.length} / 1024</small></label><button disabled={active||!initialPrompt} onClick={()=>setPrompt(initialPrompt)}>使用最新对话描述</button></div>
   :<label>参考图片<input aria-label="参考图片" type="file" accept="image/png,image/jpeg,image/webp" disabled={active} onChange={event=>{setFile(event.target.files?.[0]??null);reference.current=null;}}/><small>PNG、JPG 或 WebP，最大 10 MiB。图片会发送给 Tripo。</small></label>}
  <p className="tripo-cost">点击生成会将所选描述或图片发送到 Tripo，并按你的 Tripo 账户计费。</p>
  <div className="tripo-actions"><button className="primary" disabled={active||!!current||jobs.isPending||!!jobs.error||!settings.data?.configured||(input==='text'?(!prompt.trim()||prompt.length>1024):!file)} onClick={()=>submit.mutate()}>使用 Tripo 生成模型</button>
   {current&&!active&&<button onClick={()=>{setSelectedId('');requestId.current=crypto.randomUUID();collect.reset();submit.reset();setNotice('可以提交一个新的 Tripo 任务。');}}>新建生成任务</button>}
  </div>
  {jobs.data&&jobs.data.length>0&&<label>生成记录<select value={current??''} onChange={event=>{setSelectedId(event.target.value);if(!event.target.value)requestId.current=crypto.randomUUID();collect.reset();submit.reset();}}><option value="">新任务</option>{jobs.data.map(item=><option key={item.id} value={item.id}>{item.id.slice(-8)} · {statusNames[item.status]}</option>)}</select></label>}
  {job.data&&<div className="tripo-job"><strong role="status">{statusNames[job.data.status]??job.data.status} · {job.data.progress}%</strong><progress max={100} value={job.data.progress}/>
   <small>任务：{job.data.task_id??job.data.id}</small>{job.data.error&&<p role="alert">{job.data.error}</p>}
   <button onClick={()=>void job.refetch()} disabled={job.isFetching}>刷新状态</button>
   {(job.data.status==='success'||collect.isError)&&<button disabled={collect.isPending} onClick={()=>collect.mutate(job.data!.id)}>{collect.isPending?'下载模型中…':'获取生成文件'}</button>}
   {job.data.local_url&&<><div className="tripo-preview"><CardModelPreview url={job.data.local_url} label="Tripo 生成模型预览"/></div><a href={job.data.local_url} download>下载 GLB ↗</a><button disabled={imported.isPending||!!job.data.asset_id} onClick={()=>imported.mutate(job.data!.id)}>{imported.isPending?'Blender 检查与导入中…':job.data.asset_id?'已导入当前卡片':'导入当前卡片并检查'}</button></>}
  </div>}
  {[settings.error,jobs.error,job.error,save.error,submit.error,collect.error,imported.error].filter(Boolean).map((error,index)=><p role="alert" key={index}>{(error as Error).message}</p>)}
  {notice&&<p role="status">{notice}</p>}
 </section>;
}
