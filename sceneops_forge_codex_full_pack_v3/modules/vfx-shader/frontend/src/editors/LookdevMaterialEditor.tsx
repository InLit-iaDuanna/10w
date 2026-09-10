import { ApiError } from '@sceneops/api-client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { environmentSceneClient, environmentAssetsKey } from '@sceneops/world-composer-frontend';
import { useMutation, useQuery } from '@tanstack/react-query';
import type { LookdevMaterialEditorProps } from '../lookdev-contract';
import { createLookdevClient, type LookdevDocument, type LookdevTarget } from '../lookdev-client';
import { parseProject, selectedMaterial, isolateMaterialSlot, getExportWarnings, type LookdevProject, type LookdevOperation, type Selection } from '../core/lookdev';
import { inspectImportedScene, loadGlbScene } from '../core/three-lookdev';
import { disposeAsset } from '../core/render-scene';
import { editLookdev, moveLookdevHistory, storeLookdevHistory, restoreLookdevHistory, type LookdevHistory } from '../lookdev-history';
import { ThreeViewport, type ThreeViewportHandle } from '../LookdevViewport';
import { decodeProject } from '../core/project-package';
import { LookdevInspector } from './LookdevInspector';
import './lookdev.css';

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
  anchor.href = url; anchor.download = name; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export default function LookdevMaterialEditor(props: LookdevMaterialEditorProps) {
  const projectId = props.context.projectId;
  if (!projectId) return <div className="lookdev-empty"><h2>材质与灯光</h2><p>先选择项目，再选择要编辑的资产。</p></div>;
  return <LookdevAssetTarget {...props} projectId={projectId}/>;
}
function LookdevAssetActions(props: LookdevMaterialEditorProps) {
  const input = useRef<HTMLInputElement>(null);
  const imported = useMutation({mutationFn: async (file: File) => {
    if (!props.onImportModel) throw new Error('宿主尚未连接模型导入服务。');
    await props.onImportModel(file);
  }});
  return <div className="lookdev-toolbar">
    {props.onImportModel && <><input ref={input} type="file" accept=".glb,.fbx" hidden onChange={event=>{
      const file=event.target.files?.[0]; event.target.value=''; if(file) imported.mutate(file);
    }}/><button disabled={imported.isPending} onClick={()=>input.current?.click()}>{imported.isPending?'正在导入并检查…':'打开本地模型'}</button></>}
    {props.onOpenAssetLibrary && <button onClick={props.onOpenAssetLibrary}>浏览 3D 库</button>}
    {imported.error && <span role="alert">{imported.error.message}</span>}
  </div>;
}
function LookdevAssetTarget(props:LookdevMaterialEditorProps & {projectId:string}) {
  const assetId=props.localState.assetId ?? props.context.selectedAssetIds[0];
  const assets=useQuery({queryKey:environmentAssetsKey(props.projectId),queryFn:({signal})=>environmentSceneClient.assets(props.projectId,signal),retry:false});
  const assetVersion=props.localState.assetVersion ?? assets.data?.find(asset=>asset.id===assetId)?.current_version;
  if(assetId&&assetVersion)return <BoundLookdevEditor key={`${props.projectId}:${assetId}:${assetVersion}:${props.localState.sceneInstanceId}`} {...props} assetId={assetId} localState={{...props.localState,assetId,assetVersion,assetTitle:assets.data?.find(asset=>asset.id===assetId)?.title}}/>;
  return <div className="lookdev-empty"><h2>材质与灯光</h2><LookdevAssetActions {...props}/><p>选择一个已保存模型，编辑其当前资产版本。</p>
    {assets.isPending&&<p role="status">正在读取项目资产…</p>}
    {assets.error&&<p role="alert">{assets.error.message}<button onClick={()=>assets.refetch()}>重试</button></p>}
    {assets.data?.length===0&&<p>项目还没有已保存模型。请在模型与资产工具中导入或保存模型后再打开。</p>}
    {assetId&&assets.isSuccess&&!assetVersion&&<p role="alert">当前资产不在项目目录中，请重新选择。</p>}
    <div className="lookdev-asset-list">{assets.data?.map(asset=><button key={asset.id} onClick={()=>props.updateLocalState({assetId:asset.id,assetVersion:asset.current_version})}>{asset.title}<span>v{asset.current_version}</span></button>)}</div>
  </div>;
}

function BoundLookdevEditor(props: LookdevMaterialEditorProps & {projectId: string; assetId: string}) {
  const { projectId, assetId } = props;
  const api = useMemo(() => createLookdevClient(projectId), [projectId]);
  const target = useMemo<LookdevTarget>(() => ({ asset_id:assetId, asset_version:props.localState.assetVersion!,
    scene_instance_id:props.localState.sceneInstanceId ?? null, sceneops_id:props.localState.sceneopsId ?? null, material_slot:props.localState.materialSlot ?? null }), [assetId, props.localState.assetVersion, props.localState.sceneInstanceId, props.localState.sceneopsId, props.localState.materialSlot]);
  const loaded = useQuery({queryKey:['lookdev',projectId,target], queryFn:async ({signal}) => {
    const [bytes,documents,bindings,scene] = await Promise.all([api.source(target,signal),api.list({...target,scene_instance_id:null},signal),api.bindings(signal),props.localState.sceneVersion===undefined?environmentSceneClient.get(projectId,signal):Promise.resolve(null)]);
    const applied=bindings.find(binding=>binding.asset_id===target.asset_id && binding.asset_version===target.asset_version && (!target.scene_instance_id || !binding.scene_instance_id || binding.scene_instance_id===target.scene_instance_id));
    const previous=applied?documents.find(doc=>doc.id===applied.document_id):undefined;
    const matching=documents.filter(doc=>doc.target.asset_version===target.asset_version && (doc.target.scene_instance_id??null)===(target.scene_instance_id??null));
    // An applied catalog version starts a new document bound to that exact binary,
    // retaining its saved Shader graph rather than mistaking the GLB for the whole result.
    if(!matching.length && previous)documents.push({...previous,id:crypto.randomUUID(),version:0,target,state:applied!.state,runtime_module:applied!.runtime_module,history:[]});
    return {bytes,documents,sceneVersion:scene?.version ?? props.localState.sceneVersion};
  }, refetchOnWindowFocus:false, staleTime:Infinity, gcTime:0, retry:false});
  if (loaded.isPending) return <div className="lookdev-empty" role="status">{"\u6b63\u5728\u8bfb\u53d6\u8d44\u4ea7..."}</div>;
  if (loaded.error) return <div className="lookdev-empty" role="alert"><p>{loaded.error.message}</p><button onClick={() => loaded.refetch()}>{"\u91cd\u8bd5"}</button></div>;
  return <DecodedLookdevEditor {...props} localState={{...props.localState,sceneVersion:loaded.data!.sceneVersion}} api={api} target={target} bytes={loaded.data!.bytes} documents={loaded.data!.documents}/>;
}
function DecodedLookdevEditor(props: LookdevMaterialEditorProps & {projectId:string;assetId:string;api:ReturnType<typeof createLookdevClient>;target:LookdevTarget;bytes:ArrayBuffer;documents:LookdevDocument[]}) {
  const [loaded,setLoaded]=useState<{content:Awaited<ReturnType<typeof loadGlbScene>>;project:LookdevProject;document:LookdevDocument;bytes:ArrayBuffer}|null>(null);
  const [error,setError]=useState('');
  const [attempt,setAttempt]=useState(0);
  useEffect(()=>{
    let stopped=false;let source:Awaited<ReturnType<typeof loadGlbScene>>|null=null;
    loadGlbScene(props.bytes).then(content=>{
      source=content;if(stopped){disposeAsset(content);return;}
      const existing=props.documents.filter(d=>d.target.asset_version===props.target.asset_version && (d.target.scene_instance_id??null)===(props.target.scene_instance_id??null)).sort((a,b)=>(b.updated_at??'').localeCompare(a.updated_at??''))[0];
      const project=existing?parseProject(existing.state):inspectImportedScene(content,`${props.assetId}.glb`);
      if(existing)restoreLookdevHistory(project,existing.history);
      const now=new Date().toISOString();
      const document:LookdevDocument=existing??{id:crypto.randomUUID(),project_id:props.projectId,version:0,target:props.target,state:project,history:[],created_at:now,updated_at:now};
      setLoaded({content,project,document,bytes:props.bytes});
    }).catch(reason=>{if(!stopped)setError((reason as Error).message);});
    return ()=>{stopped=true;if(source)disposeAsset(source);};
  },[props.bytes,props.documents,props.target,props.projectId,props.assetId,attempt]);
  if(error)return <div className="lookdev-empty" role="alert"><p>{error}</p><button onClick={()=>{setError('');setAttempt(value=>value+1);}}>{"\u91cd\u8bd5"}</button></div>;
  if(!loaded)return <div className="lookdev-empty" role="status">{"\u6b63\u5728\u51c6\u5907 GPU \u6a21\u578b..."}</div>;
  return <ReadyLookdevEditor {...props} loaded={loaded}/>;
}
function ReadyLookdevEditor({api,loaded,...props}: LookdevMaterialEditorProps & {projectId:string;assetId:string;api:ReturnType<typeof createLookdevClient>;loaded:{content:Awaited<ReturnType<typeof loadGlbScene>>;project:LookdevProject;document:LookdevDocument;bytes:ArrayBuffer}}) {
  const viewport = useRef<ThreeViewportHandle>(null);
  const importInput = useRef<HTMLInputElement>(null);
  const proposalAbort = useRef<AbortController | null>(null);
  const proposalSettled=useRef<Promise<void>>(Promise.resolve());
  const [history,setHistory] = useState<LookdevHistory>(()=>restoreLookdevHistory(loaded.project,loaded.document.history));
  const current = useRef(history); const busy = useRef(false);
  const [document,setDocument] = useState(loaded.document);
  const [saved,setSaved] = useState(loaded.project);
  const appliedVersion = useRef(loaded.document.target.asset_version);
  const appliedSceneVersion = useRef(props.localState.sceneVersion);
  const [selection,setSelection] = useState<Selection>(() => { const object=loaded.project.objects.find(o => o.id===props.localState.sceneopsId) ?? loaded.project.objects[0];return {objectId:object.id,slot:props.localState.materialSlot ?? object.materialSlots[0].slot}; });
  const [ready,setReady] = useState(false); const [working,setWorking] = useState(false);
  const [error,setError] = useState(''); const [notice,setNotice] = useState('');
  const [comparing,setComparing] = useState(false); const [lighting,setLighting] = useState(false);
  const project = history.present; const material = selectedMaterial(project,selection);
  const callbacks = useRef(props); callbacks.current=props;
  useEffect(() => { callbacks.current.onDirtyChange?.(project!==saved); },[project,saved]);
  useEffect(() => () => {proposalAbort.current?.abort();callbacks.current.onConversationTargetChange?.(null);},[]);
  const transaction = useCallback(async (next: LookdevHistory, signal?:AbortSignal) => {
    await viewport.current!.apply(next.present,undefined,false,signal);
    current.current=next;setHistory(next);setComparing(false);setError('');
  },[]);
  async function edit(operations:LookdevOperation[],summary:string) {
    if(proposalAbort.current){proposalAbort.current.abort();await proposalSettled.current;}
    if(busy.current) return; busy.current=true;setWorking(true);
    try {
      const original=current.current;
      const isolated=isolateMaterialSlot(original.present,selection.objectId,selection.slot);
      const scoped=operations.map(operation=>'targetId' in operation && operation.targetId===material?.id && operation.kind.startsWith('material.')?{...operation,targetId:isolated.materialId}:operation);
      const next=editLookdev({...original,present:isolated.project},scoped,'manual',summary);
      await transaction({...next,past:[...original.past,original.present]});
    }
    catch(e){setError((e as Error).message);} finally {busy.current=false;setWorking(false);}
  }
  useEffect(() => {
    if(props.suspended || !ready || !material) {callbacks.current.onConversationTargetChange?.(null);return;}
    callbacks.current.onConversationTargetChange?.({projectId:props.projectId,label:`${props.localState.assetTitle??"模型"} · ${material.name}`,lighting,setLighting,history:api.history,
      submit:async (prompt,signal,requestId) => {
        if(busy.current) throw new Error('材质正在更新，请稍后再试。');
        busy.current=true;setWorking(true);const snapshot=current.current;
        const isolated=isolateMaterialSlot(snapshot.present,selection.objectId,selection.slot);
        const controller=new AbortController();proposalAbort.current=controller;
        let finishRequest!:()=>void;proposalSettled.current=new Promise<void>(resolve=>{finishRequest=resolve;});
        const turnId=requestId??crypto.randomUUID();const createdAt=new Date().toISOString();let accepted=false;
        const cancel=()=>controller.abort();signal?.addEventListener('abort',cancel,{once:true});if(signal?.aborted)controller.abort();
        try {
          const proposal=await api.propose({document:{...document,target:{...document.target,sceneops_id:selection.objectId,material_slot:selection.slot},state:isolated.project},prompt,allow_lighting:lighting,material_ids:[isolated.materialId],turn_id:turnId},controller.signal);
          if(controller.signal.aborted) throw new Error('材质请求已取消。');
          if(current.current!==snapshot) throw new Error('材质已变化，请重新提交。');
          if(proposal.operations.length){const next=editLookdev({...snapshot,present:isolated.project},proposal.operations,'ai',proposal.summary,{materialIds:[isolated.materialId],lightIds:snapshot.present.lights.map(l=>l.id),lighting});await transaction({...next,past:[...snapshot.past,snapshot.present]},controller.signal);}
          const status=proposal.operations.length?'applied' as const:proposal.status==='declined'?'declined' as const:'noop' as const;
          accepted=true;
          let summary=proposal.summary;
          try {await api.finish(turnId,{status,summary});}
          catch(recordError){summary+=`（预览结果已保留，但会话记录保存失败：${(recordError as Error).message}）`;setError(summary);}
          setNotice(summary);return {summary,status,turnId,createdAt};
        } catch(e){
          const message=(e as Error).message;
          if(!accepted){try{await api.finish(turnId,{status:controller.signal.aborted?'cancelled':'failed',summary:message});}catch(recordError){if(recordError instanceof ApiError && recordError.status===404)throw e;setError(`${message}；会话记录未保存：${(recordError as Error).message}`);throw e;}}
          setError(message);throw e;
        } finally {signal?.removeEventListener('abort',cancel);proposalAbort.current=null;busy.current=false;setWorking(false);finishRequest();}
      }});
    return ()=>callbacks.current.onConversationTargetChange?.(null);
  },[props.suspended,ready,material?.id,material?.name,selection.objectId,selection.slot,lighting,api,document,transaction,props.projectId,props.assetId,props.localState.assetTitle]);
  const save = useMutation({mutationFn:async () => {
    if(busy.current) throw new Error('材质正在更新，请稍后再试。');
    busy.current=true;
    try {
      const snapshot=current.current.present;
      const result=await api.save({...document,state:snapshot,history:storeLookdevHistory(current.current)});
      setDocument(result);setSaved(snapshot);setNotice(`已保存材质工程版本 ${result.version}`);return result;
    } finally {busy.current=false;}
  }});
  async function action(run:()=>Promise<void>) {if(busy.current)return;busy.current=true;setWorking(true);try{await run();setError('');}catch(e){setError((e as Error).message);}finally{busy.current=false;setWorking(false);}}
  async function exportSaved(format:'pbr-glb'|'shader-zip'|'luma-zip') {
    const snapshot=current.current.present;
    const savedDocument=document.version&&snapshot===saved?document:await api.save({...document,state:snapshot,history:storeLookdevHistory(current.current)});
    setDocument(savedDocument);setSaved(snapshot);
    const artifact=await api.export({document_id:savedDocument.id,document_version:savedDocument.version,format});
    download(new Blob([await api.download(artifact)],{type:artifact.media_type}),artifact.filename);
    setNotice(artifact.warnings?.length?artifact.warnings.join(' '):`已导出材质版本 ${savedDocument.version}。`);
  }
  const disabled=!ready||working||save.isPending;
  return <div className="lookdev-editor" onKeyDown={event=>{
    const input=event.target as HTMLElement;
    if(!(event.metaKey||event.ctrlKey))return;
    const key=event.key.toLowerCase();
    if(key==='s'){event.preventDefault();if(!disabled)save.mutate();}
    if(key==='z'||key==='y'){if(input.closest('input,textarea,[contenteditable="true"]'))return;event.preventDefault();if(!disabled){const direction=key==='y'||event.shiftKey?'redo':'undo';if(current.current[direction==='undo'?'past':'future'].length)void action(()=>transaction(moveLookdevHistory(current.current,direction)));}}
  }} tabIndex={-1}>
    <LookdevAssetActions {...props}/>
    <div className="lookdev-toolbar"><strong>{props.localState.assetTitle??"模型"}</strong><span className="muted"> · v{document.target.asset_version}</span><span className="badge">{ready ? "预览就绪" : error ? "预览不可用" : "正在准备预览"}</span><span className="lookdev-spacer"/>
<div className="lookdev-selection"><label>当前材质<select value={`${selection.objectId}:${selection.slot}`} disabled={disabled} onChange={e=>{const item=project.objects.flatMap(o=>o.materialSlots.map(s=>({objectId:o.id,slot:s.slot}))).find(s=>`${s.objectId}:${s.slot}`===e.target.value);if(item)setSelection(item);}}>{project.objects.flatMap(object=>object.materialSlots.map(slot=><option key={`${object.id}:${slot.slot}`} value={`${object.id}:${slot.slot}`}>{object.name} · 槽 {slot.slot} · {project.materials.find(m=>m.id===slot.materialId)?.name}</option>))}</select></label><button disabled={disabled} onClick={()=>viewport.current?.frame()}>适应视图</button></div>
      <button disabled={disabled||!history.past.length} onClick={()=>action(()=>transaction(moveLookdevHistory(current.current,'undo')))}>撤销</button>
      <button disabled={disabled||!history.future.length} onClick={()=>action(()=>transaction(moveLookdevHistory(current.current,'redo')))}>重做</button>
      <button disabled={disabled} aria-pressed={comparing} onClick={()=>action(async()=>{await viewport.current!.compare(comparing?null:saved);setComparing(!comparing);})}>{comparing?'退出对比':'对比已保存版本'}</button>
      <button disabled={disabled||!material} onClick={()=>action(async()=>{
        const result=isolateMaterialSlot(current.current.present,selection.objectId,selection.slot);
        if(result.isolated) await transaction({past:[...current.current.past,current.current.present],present:result.project,future:[]});
        setNotice(result.isolated?'当前材质槽已独立编辑。':'当前材质已经独立。');
      })}>独立此材质槽</button>
      <button disabled={disabled} onClick={()=>save.mutate()}>保存版本{project!==saved?' *':''}</button>
      <button disabled={disabled} onClick={props.onOpenConversation}>在主对话调整</button>
    </div>
    {(error||save.error) && <div className="notice error" role="alert">{error||save.error?.message}</div>}
    {notice && <div className="lookdev-notice" role="status">{notice}</div>}
    <div className="lookdev-body"><div className="lookdev-canvas"><ThreeViewport ref={viewport} initialProject={loaded.project} initialContent={loaded.content} suspended={props.suspended} onReady={()=>setReady(true)} onSelect={setSelection} onStats={()=>{}} onError={message=>{setError(message);setReady(false);}}/>
      
    </div>{material && <LookdevInspector project={project} material={material} disabled={!ready||save.isPending||(working&&!proposalAbort.current)} edit={edit}/>}</div>
    <div className="lookdev-notice">{getExportWarnings(project).join(" ")}</div>
    <div className="lookdev-toolbar"><span className="lookdev-spacer"/>
      <input ref={importInput} type="file" accept=".zip,.json" hidden onChange={e=>{const file=e.target.files?.[0];e.target.value='';if(file) action(async()=>{
        const bytes=await file.arrayBuffer();
        if(file.name.endsWith('.zip')){
          const imported=await decodeProject(bytes);
          await transaction(restoreLookdevHistory(imported.project,[{kind:'lookdev.history@1',...imported.history}]));
          setNotice('工程及编辑历史已恢复到当前资产草稿。');
        }else{
          const imported=parseProject(JSON.parse(new TextDecoder().decode(bytes)));
          await transaction({past:[...current.current.past,current.current.present],present:imported,future:[]});
          setNotice('工程已载入当前资产草稿。');
        }
      });}}/>
      <button disabled={disabled} onClick={()=>importInput.current?.click()}>载入工程</button>
      <details className="lookdev-export"><summary>导出</summary><div>
      <button disabled={disabled} onClick={()=>action(async()=>download(await viewport.current!.screenshot(),'材质预览.png'))}>导出 PNG</button>
      <button disabled={disabled} onClick={()=>action(()=>exportSaved('luma-zip'))}>导出工程 ZIP</button>
      <button disabled={disabled||!project.materials.some(item=>item.shaderGraph||item.procedural.type!=='none')} onClick={()=>action(()=>exportSaved('shader-zip'))}>导出 Shader</button>
      <button disabled={disabled} onClick={()=>action(()=>exportSaved('pbr-glb'))}>导出 GLB</button></div></details>
      <button disabled={disabled} onClick={()=>action(async()=>{
        const snapshot=current.current.present;
        const savedDocument=await api.save({...document,state:snapshot,history:storeLookdevHistory(current.current)});
        setDocument(savedDocument);setSaved(snapshot);
        const result=await api.apply({document_id:savedDocument.id,document_version:savedDocument.version,expected_target_version:appliedVersion.current,expected_scene_version:appliedSceneVersion.current});
        setNotice(props.localState.entityDefinitionId ? `已保存资产候选 v${result.asset_version}；请回到功能包采用此版本，再更新试玩。` : `已应用至资产版本 ${result.asset_version}；请更新作品并确认试玩效果。`);
        appliedVersion.current=result.asset_version;
        appliedSceneVersion.current=result.scene_version ?? appliedSceneVersion.current;
        props.onApplied?.(result);
      })}>{props.localState.entityDefinitionId ? '保存为资产候选' : '应用到游戏'}</button>
    </div>
  </div>;
}
export { LookdevMaterialEditor };
