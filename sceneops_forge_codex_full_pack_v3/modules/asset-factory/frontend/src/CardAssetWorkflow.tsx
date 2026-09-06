import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CardModelPreview, MODEL_ROTATION_IDENTITY, type CardModelPreviewHandle, type ModelRotationQuaternion } from './CardModelPreview.tsx';
import { cardAssetClient, cardAssetFileUrl, cardAssetKey, projectAssetLibraryKey, type CardAssetList, type CardAssetRecord } from './cardAssetClient.ts';
import './card-asset-workflow.css';

type Message = { id: string; role: string; text: string; replyTo?: string; modelingBlock?: string };
type LiveUpdateJob = { triggerMessageId: string; modelingBlock: string;
  transcript: {role:string;text:string}[]; retryFailed?: boolean; modelRotation?: ModelRotationQuaternion };

const MODELING_BLOCKS = [
  {id:'shape', label:'轮廓', detail:'用途与整体造型'},
  {id:'scale', label:'比例', detail:'尺寸与部件关系'},
  {id:'surface', label:'表面', detail:'材质与配色'},
  {id:'interaction', label:'交互', detail:'摆放与使用约束'},
] as const;

function versionRotation(version: {model_rotation_quaternion_xyzw?: readonly [number, number, number, number] | null} | undefined): ModelRotationQuaternion {
  const value = version?.model_rotation_quaternion_xyzw;
  return value ? [value[0], value[1], value[2], value[3]] : MODEL_ROTATION_IDENTITY;
}

function sameRotation(left: ModelRotationQuaternion, right: ModelRotationQuaternion) {
  const dot = left.reduce((total, value, index) => total + value * right[index], 0);
  return Math.abs(dot) >= 1 - 1e-6;
}

export type CardAssetWorkflowProps = { projectId: string; cardId: string; source: 'import'|'create';
  sessionId: string; messages: Message[]; onCreateAnother?: () => void; onOpenEnvironment?: () => void;
  observeConversation?: boolean; presentation?: 'workflow'|'scene' };

export function CardAssetWorkflow({projectId, cardId, source, sessionId, messages, onCreateAnother, onOpenEnvironment,
  observeConversation = true, presentation = 'workflow'}: CardAssetWorkflowProps) {
  const cache = useQueryClient();
  const key = cardAssetKey(projectId, cardId);
  const query = useQuery({queryKey:key, queryFn:({signal}) => cardAssetClient.list(projectId, cardId, signal), retry:false});
  const libraryKey = projectAssetLibraryKey(projectId);
  const library = useQuery({queryKey:libraryKey, queryFn:({signal}) => cardAssetClient.library(projectId, signal), retry:false});
  const [importFile, setImportFile] = useState<File|null>(null);
  const [referenceFile, setReferenceFile] = useState<File|null>(null);
  const [referenceId, setReferenceId] = useState<string|null>(null);
  const [targets, setTargets] = useState<Record<string,string>>({});
  const [selectedVersions, setSelectedVersions] = useState<Record<string,number>>({});
  const [modelRotations, setModelRotations] = useState<Record<string,ModelRotationQuaternion>>({});
  const [notice, setNotice] = useState<{text:string;kind:'success'|'error'}|null>(null);
  const [queue, setQueue] = useState<LiveUpdateJob[]>([]);
  const [failedJob, setFailedJob] = useState<LiveUpdateJob|null>(null);
  const [cameraAngle, setCameraAngle] = useState(30);
  const [sceneShare, setSceneShare] = useState(() => Math.min(76, Math.max(36,
    Number(localStorage.getItem('sceneops.environment.scene-share.v1')) || 62)));
  const observed = useRef<{sessionId:string;messageIds:Set<string>}|null>(null);
  const preview = useRef<CardModelPreviewHandle>(null);
  const previewHandles = useRef<Record<string,CardModelPreviewHandle|null>>({});
  const sceneRoot = useRef<HTMLElement>(null);
  const resizingScene = useRef(false);
  const allAssets = query.data?.assets ?? [];
  const assets = source === 'create'
    ? allAssets.filter(asset => asset.source_type === 'generated' && asset.session_id === sessionId)
    : allAssets.filter(asset => asset.source_type === 'import');
  const hasSessionDraft = source === 'create' && assets.length > 0;
  const activeAsset = source === 'create'
    ? assets.find(asset => asset.source_type === 'generated' && asset.session_id === sessionId)
    : assets[0];
  const inheritedModelRotation = activeAsset
    ? modelRotations[activeAsset.id] ?? versionRotation(activeAsset.versions?.at(-1))
    : MODEL_ROTATION_IDENTITY;
  const refresh = async () => { await cache.invalidateQueries({queryKey:key}); };

  const imported = useMutation({mutationFn: async () => {
    if (!importFile) throw new Error('请先选择 GLB 或 FBX 文件。');
    return cardAssetClient.import(projectId, cardId, sessionId, importFile);
  }, onSuccess: async () => { setImportFile(null); setNotice({text:'Blender 已读取模型，右侧可检查真实预览。',kind:'success'}); await refresh(); },
    onError:async error => { setNotice({text:error.message,kind:'error'}); await refresh(); }});

  const liveUpdated = useMutation({mutationFn: async (job: LiveUpdateJob) => {
    let reference_id = referenceId ?? undefined;
    if (referenceFile && !reference_id) {
      reference_id = (await cardAssetClient.reference(projectId, cardId, referenceFile)).id;
      setReferenceId(reference_id);
    }
    return cardAssetClient.liveUpdate(projectId, cardId, {
      session_id:sessionId,
      trigger_message_id:job.triggerMessageId,
      modeling_block:job.modelingBlock,
      transcript:job.transcript,
      retry_failed:!!job.retryFailed,
      model_rotation_quaternion_xyzw:job.modelRotation ?? inheritedModelRotation,
      ...(reference_id ? {reference_id} : {}),
    });
  }, onSuccess: async (result, job) => {
    cache.setQueryData<CardAssetList>(key, current => current ? {
      ...current,
      assets:[result.asset, ...current.assets.filter(item => item.id !== result.asset.id)],
      proposals:[result.proposal, ...current.proposals.filter(item => item.id !== result.proposal.id)],
    } : current);
    setReferenceFile(null);
    setFailedJob(null);
    setQueue(current => current.filter(item => item.triggerMessageId !== result.proposal.trigger_message_id));
    const createdVersion = (result.asset.versions ?? []).find(item => item.number === result.asset.current_version);
    setModelRotations(current => current[result.asset.id] ? current : {
      ...current,
      [result.asset.id]:job.modelRotation ?? versionRotation(createdVersion),
    });
    setNotice({text:result.reused ? `本轮已生成过，已恢复 v${result.asset.current_version}。` : `草稿 v${result.asset.current_version} 已更新。`,kind:'success'});
    await refresh();
  }, onError: async (error, job) => {
    setQueue(current => current.filter(item => item.triggerMessageId !== job.triggerMessageId));
    setFailedJob({...job, retryFailed:false});
    setNotice({text:error.message,kind:'error'});
    await refresh();
  }});

  const normalized = useMutation({mutationFn:({asset,target}:{asset:CardAssetRecord;target:number}) => cardAssetClient.normalize(asset.id,target),
    onSuccess:async result => {
      setSelectedVersions(current => ({...current,[result.id]:result.current_version}));
      setNotice({text:'已追加归一化版本；之前的草稿仍可切换查看。',kind:'success'}); await refresh();
    }, onError:async error => { setNotice({text:error.message,kind:'error'}); await refresh(); }});
  const savedToLibrary = useMutation({mutationFn:({assetId,version,modelRotation}:{assetId:string;version:number;modelRotation:ModelRotationQuaternion}) =>
    cardAssetClient.saveToLibrary(assetId, version, modelRotation), onSuccess:async (result, variables) => {
      cache.setQueryData(libraryKey, (current:typeof library.data) => current
        ? [result.entry, ...current.filter(item => item.id !== result.entry.id)] : [result.entry]);
      setSelectedVersions(current => ({...current,[variables.assetId]:result.entry.current_version}));
      setModelRotations(current => current[variables.assetId] ? current : {
        ...current,
        [variables.assetId]:versionRotation(result.entry.versions.find(item => item.source_version === result.entry.current_version)),
      });
      setNotice({text:result.version_created ? '已按当前模型轴向校准并存入项目资产库。' : '这个版本已经按当前轴向校准存入资产库。',kind:'success'});
      await refresh();
      await cache.invalidateQueries({queryKey:libraryKey});
    }, onError:error => setNotice({text:error.message,kind:'error'})});

  useEffect(() => {
    if (!observeConversation) {
      observed.current = null;
      setQueue([]);
      setFailedJob(null);
      return;
    }
    const userMessages = messages.filter(message => message.role === 'user' && message.text.trim());
    if (!observed.current || observed.current.sessionId !== sessionId) {
      observed.current = {sessionId, messageIds:new Set(userMessages.map(message => message.id))};
      setQueue([]); setFailedJob(null); setNotice(null);
      return;
    }
    const fresh = userMessages.filter(message => !observed.current!.messageIds.has(message.id));
    if (!fresh.length) return;
    fresh.forEach(message => observed.current!.messageIds.add(message.id));
    if (source === 'create' && !hasSessionDraft) return;
    const jobs = fresh.map(message => {
      const messageIndex = messages.findIndex(item => item.id === message.id);
      const turnIndex = userMessages.findIndex(item => item.id === message.id);
      const fallbackBlock = MODELING_BLOCKS[turnIndex]?.id ?? 'refinement';
      return {triggerMessageId:message.id, modelingBlock:message.modelingBlock ?? fallbackBlock,
        transcript:messages.slice(0, messageIndex + 1)
          .filter(item => (item.role === 'user' || item.role === 'assistant') && item.text.trim())
          .map(item => ({role:item.role,text:item.text}))};
    });
    setQueue(current => [...current, ...jobs.filter(job => !current.some(item => item.triggerMessageId === job.triggerMessageId))]);
  }, [messages, observeConversation, sessionId, source, hasSessionDraft]);

  useEffect(() => {
    if (!observeConversation || source !== 'create' || !query.isSuccess || liveUpdated.isPending || failedJob || !queue.length) return;
    setNotice(null);
    liveUpdated.mutate(queue[0]!);
  }, [source, query.isSuccess, queue, failedJob, liveUpdated.isPending, observeConversation]);

  const latestProposal = query.data?.proposals.find(item => item.session_id === sessionId) ?? null;
  const completedBlocks = useMemo(() => {
    const ids = new Set<string>();
    messages.filter(message => message.role === 'user').forEach((message, index) =>
      ids.add(message.modelingBlock ?? MODELING_BLOCKS[index]?.id ?? 'refinement'));
    return ids;
  }, [messages]);
  const currentBlock = MODELING_BLOCKS.find(block => !completedBlocks.has(block.id))?.id ?? 'refinement';
  const busy = imported.isPending || liveUpdated.isPending || normalized.isPending || savedToLibrary.isPending;
  const size = (value:readonly number[]|null|undefined) => value ? value.map(item => Number(item.toFixed(3))).join(' × ') + ' m' : '—';
  const resizeScene = (clientY:number) => {
    const bounds = sceneRoot.current?.getBoundingClientRect();
    if (!bounds) return;
    setSceneShare(Math.min(76, Math.max(36, ((clientY - bounds.top) / bounds.height) * 100)));
  };
  useEffect(() => { localStorage.setItem('sceneops.environment.scene-share.v1', String(sceneShare)); }, [sceneShare]);
  if (query.isPending) return <p role="status" className="card-asset-status">读取当前 Git 分支的模型…</p>;
  if (query.error) return <p role="alert" className="card-asset-status">{query.error.message} <button onClick={() => void query.refetch()}>重试</button></p>;

  const sceneAsset = assets[0];
  const sceneVersions = sceneAsset?.versions ?? [];
  const sceneVersionNumber = sceneAsset ? selectedVersions[sceneAsset.id] ?? sceneAsset.current_version : undefined;
  const sceneVersion = sceneVersions.find(item => item.number === sceneVersionNumber) ?? sceneVersions.at(-1);
  const sceneModelRotation = sceneAsset ? modelRotations[sceneAsset.id] ?? versionRotation(sceneVersion) : MODEL_ROTATION_IDENTITY;
  const sceneGenerationPending = liveUpdated.isPending || sceneAsset?.status === 'processing';
  const sceneLibraryVersion = sceneAsset && sceneVersion
    ? library.data?.find(item => item.source_asset_id === sceneAsset.id)?.versions.find(item => item.source_version === sceneVersion.number)
    : undefined;
  const sceneVersionSaved = !!sceneLibraryVersion && sameRotation(
    versionRotation(sceneLibraryVersion), sceneModelRotation);
  if (presentation === 'scene') return <section ref={sceneRoot} className="card-model-scene-workflow"
    style={{'--card-model-scene-share':`${sceneShare}%`} as CSSProperties} aria-label="当前模型场景">
    <section className="card-model-scene-card" aria-label="当前模型预览">
      <div className="card-model-scene-status"><div className="card-model-scene-title"><span>{sceneVersion ? `模型 v${sceneVersion.number}` : '模型草稿'}</span>
        <strong>{sceneAsset?.title ?? (sceneGenerationPending ? '正在生成模型' : '等待确认建模')}</strong></div>
        <div className="card-model-scene-meta">{sceneGenerationPending
          ? <span className="card-model-generation-status" role="status" aria-live="polite"><i/>正在生成中</span>
          : <small>Three.js · 米制网格</small>}
          {!!sceneVersions.length && <div className="card-version-strip card-model-top-versions" aria-label="模型版本">{sceneVersions.map(item => <button key={item.number} type="button"
            aria-pressed={item.number === sceneVersion?.number} onClick={() => setSelectedVersions(current => ({...current,[sceneAsset!.id]:item.number}))}>v{item.number}</button>)}</div>}
        </div></div>
      {sceneAsset && sceneVersion ? <CardModelPreview ref={preview} label={`${sceneAsset.title} v${sceneVersion.number}`}
        url={cardAssetFileUrl(sceneAsset.id,'preview',sceneVersion.number)}
        modelRotation={sceneModelRotation} baseModelRotation={versionRotation(sceneVersion)}
        onModelRotationChange={rotation => setModelRotations(current => ({...current,[sceneAsset.id]:[...rotation] as ModelRotationQuaternion}))}/>
        : <div className="card-model-scene-empty"><strong>{source === 'import' ? '等待导入模型' : '当前需求还没有模型版本'}</strong>
          <span>{source === 'import' ? '在下方选择 GLB 或 FBX。' : '在左侧对话确认需求，然后点击“确认并建模”。'}</span></div>}
    </section>
    <div className="card-model-scene-splitter" role="separator" aria-label="调整模型预览与操作区高度" aria-orientation="horizontal"
      aria-valuemin={36} aria-valuemax={76} aria-valuenow={Math.round(sceneShare)} tabIndex={0}
      onPointerDown={event => {resizingScene.current=true;event.currentTarget.setPointerCapture(event.pointerId);resizeScene(event.clientY);}}
      onPointerMove={event => {if (resizingScene.current) resizeScene(event.clientY);}}
      onPointerUp={event => {resizingScene.current=false;event.currentTarget.releasePointerCapture(event.pointerId);}}
      onPointerCancel={() => {resizingScene.current=false;}}
      onKeyDown={event => {if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;event.preventDefault();
        setSceneShare(value => Math.min(76, Math.max(36, value + (event.key === 'ArrowUp' ? -4 : 4))));}}><span/></div>
    <section className="card-model-camera-card" aria-label="模型视角操作">
      <header><div><strong>模型视角</strong><small>拖动画布也可以自由查看</small></div>
        {sceneVersion && <span>{size(sceneVersion.dimensions_m)}</span>}</header>
      {notice && <p role={notice.kind === 'error' ? 'alert' : 'status'} className="card-asset-notice" data-kind={notice.kind}>{notice.text}</p>}
      {failedJob && <button className="card-live-retry" disabled={busy} onClick={() => {setNotice(null);liveUpdated.mutate({...failedJob,retryFailed:true});}}>重试本轮草稿</button>}
      {source === 'import' && <div className="card-asset-action"><label className="card-asset-file"><strong>{importFile?.name ?? '选择 GLB / FBX'}</strong>
        <small>{importFile ? `${(importFile.size/1024/1024).toFixed(2)} MiB` : '原文件会保留在当前卡片分支'}</small>
        <input type="file" accept=".glb,.fbx,model/gltf-binary,application/octet-stream" disabled={busy} onChange={event=>setImportFile(event.target.files?.[0] ?? null)}/></label>
        <button disabled={busy || !importFile} onClick={()=>{setNotice(null);imported.mutate();}}>{imported.isPending ? 'Blender 检查中…' : '导入并检查'}</button></div>}
      {sceneVersion && <><div className="card-model-camera-grid">
        <button type="button" onClick={() => preview.current?.zoom(.8)}>放大 ＋</button><button type="button" onClick={() => preview.current?.zoom(1.25)}>缩小 －</button>
        <button type="button" onClick={() => preview.current?.view('front')}>前视</button><button type="button" onClick={() => preview.current?.view('back')}>后视</button>
        <button type="button" onClick={() => preview.current?.view('left')}>左视</button><button type="button" onClick={() => preview.current?.view('right')}>右视</button>
        <button type="button" onClick={() => preview.current?.rotate(-cameraAngle)}>左转 {cameraAngle}°</button><button type="button" onClick={() => preview.current?.rotate(cameraAngle)}>右转 {cameraAngle}°</button>
      </div><div className="card-model-angle-row"><label>旋转角度<select value={cameraAngle} onChange={event => setCameraAngle(Number(event.target.value))}>
        {[15,30,45,90].map(value => <option key={value} value={value}>{value}°</option>)}</select></label>
        <button type="button" onClick={() => preview.current?.reset()}>复位视角</button></div>
        <section className="card-model-axis-panel" aria-label="模型三轴旋转">
          <header><strong>模型旋转 90°</strong><small>校准后续版本与项目资产轴向</small></header>
          <div><button type="button" onClick={() => preview.current?.rotateModel('x',90)}>X 轴 +90°</button>
            <button type="button" onClick={() => preview.current?.rotateModel('y',90)}>Y 轴 +90°</button>
            <button type="button" onClick={() => preview.current?.rotateModel('z',90)}>Z 轴 +90°</button>
            <button type="button" onClick={() => preview.current?.resetModel()}>复位模型</button></div>
          <small>当前校准会随之后的模型版本继承；存入资产库时会写入 GLB、FBX 和 .blend。</small>
        </section>
        <div className="card-model-scene-actions"><button type="button" disabled={busy || sceneVersionSaved}
          onClick={() => {setNotice(null);savedToLibrary.mutate({assetId:sceneAsset.id,version:sceneVersion.number,modelRotation:sceneModelRotation});}}>{sceneVersionSaved ? '已存资产库' : '存入资产库'}</button>
          {onCreateAnother && <button type="button" disabled={busy} onClick={onCreateAnother}>新建另一个</button>}
          {onOpenEnvironment && <button type="button" disabled={busy} onClick={onOpenEnvironment}>返回世界</button>}</div></>}
      {!sceneVersion && source === 'create' && <p className="card-asset-empty">首版由左侧“确认并建模”启动；之后继续对话会更新同一个模型。</p>}
    </section>
  </section>;

  return <section className="card-asset-workflow" aria-label={source === 'import' ? '导入模型工作流' : '实时新建模型工作流'}>
    {source === 'create' ? <>
      <ol className="card-model-blocks" aria-label="建模对齐阶段">{MODELING_BLOCKS.map((block, index) => <li key={block.id}
        data-state={completedBlocks.has(block.id) ? 'done' : currentBlock === block.id ? 'current' : 'pending'}>
        <span>{completedBlocks.has(block.id) ? '✓' : index + 1}</span><div><strong>{block.label}</strong><small>{block.detail}</small></div></li>)}</ol>
      <label className="card-reference-picker"><span>{referenceFile?.name ?? (referenceId ? '参考图已启用' : '参考图 · 可选')}</span>
        <small>{referenceFile ? '将在下一轮草稿使用' : 'PNG / JPEG / WebP'}</small>
        <input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy} onChange={event=>{setReferenceFile(event.target.files?.[0] ?? null);setReferenceId(null);}}/></label>
      {liveUpdated.isPending && <div className="card-live-state" role="status"><span/><div><strong>正在生成下一版</strong><small>AI 重建方案，随后由 Blender 输出 GLB</small></div></div>}
      {failedJob && <button className="card-live-retry" disabled={busy} onClick={() => {setNotice(null);liveUpdated.mutate({...failedJob,retryFailed:true});}}>重试本轮草稿</button>}
    </> : <div className="card-asset-action">
      <label className="card-asset-file"><strong>{importFile?.name ?? '选择 GLB / FBX'}</strong><small>{importFile ? `${(importFile.size/1024/1024).toFixed(2)} MiB` : '原文件会保留在当前卡片分支'}</small>
        <input type="file" accept=".glb,.fbx,model/gltf-binary,application/octet-stream" disabled={busy} onChange={event=>setImportFile(event.target.files?.[0] ?? null)}/></label>
      <button disabled={busy || !importFile} onClick={()=>{setNotice(null);imported.mutate();}}>{imported.isPending ? 'Blender 检查中…' : '导入并检查'}</button>
    </div>}

    {notice && <p role={notice.kind === 'error' ? 'alert' : 'status'} className="card-asset-notice" data-kind={notice.kind}>{notice.text}</p>}
    {!!assets.length ? <div className="card-asset-results">{assets.map(asset => {
      const versions = asset.versions ?? [];
      const selectedNumber = selectedVersions[asset.id] ?? asset.current_version;
      const version = versions.find(item => item.number === selectedNumber) ?? versions.at(-1);
      const modelRotation = modelRotations[asset.id] ?? versionRotation(version);
      const target = targets[asset.id] ?? (version ? String(Math.max(...version.dimensions_m)) : '1');
      const libraryEntry = library.data?.find(item => item.source_asset_id === asset.id);
      const libraryVersion = version && libraryEntry?.versions.find(item => item.source_version === version.number);
      const versionSaved = !!libraryVersion && sameRotation(versionRotation(libraryVersion), modelRotation);
      return <article key={asset.id} className="card-asset-result" data-status={asset.status}>
        <div className="card-asset-result-heading"><div><small>{asset.source_type === 'import' ? '已导入' : '实时草稿'}</small><h3>{asset.title}</h3></div><span>v{version?.number ?? asset.current_version}</span></div>
        {version && <><CardModelPreview label={`${asset.title} v${version.number}`} url={cardAssetFileUrl(asset.id,'preview',version.number)}
          ref={handle => { previewHandles.current[asset.id] = handle; }}
          modelRotation={modelRotation} baseModelRotation={versionRotation(version)}
          onModelRotationChange={rotation => setModelRotations(current => ({...current,[asset.id]:[...rotation] as ModelRotationQuaternion}))}/>
          <div className="card-version-strip" aria-label="模型版本">{versions.map(item => <button key={item.number} type="button"
            aria-pressed={item.number === version.number} onClick={() => setSelectedVersions(current => ({...current,[asset.id]:item.number}))}>v{item.number}</button>)}</div>
          <dl className="card-asset-metrics"><div><dt>尺寸</dt><dd>{size(version.dimensions_m)}</dd></div><div><dt>网格</dt><dd>{version.vertex_count} 顶点 · {version.triangle_count} 面</dd></div></dl>
          <section className="card-model-axis-panel" aria-label={`${asset.title} 模型三轴旋转`}>
            <header><strong>模型旋转 90°</strong><small>后续版本与入库资产会继承</small></header>
            <div><button type="button" onClick={() => previewHandles.current[asset.id]?.rotateModel('x',90)}>X 轴 +90°</button>
              <button type="button" onClick={() => previewHandles.current[asset.id]?.rotateModel('y',90)}>Y 轴 +90°</button>
              <button type="button" onClick={() => previewHandles.current[asset.id]?.rotateModel('z',90)}>Z 轴 +90°</button>
              <button type="button" onClick={() => previewHandles.current[asset.id]?.resetModel()}>复位模型</button></div>
          </section>
          <div className="card-asset-next-actions">
            <button type="button" className="primary" disabled={busy || versionSaved}
              onClick={() => {setNotice(null);savedToLibrary.mutate({assetId:asset.id,version:version.number,modelRotation});}}>{versionSaved ? '已存资产库' : '存入资产库'}</button>
            {versionSaved && source === 'create' && onCreateAnother && <button type="button" disabled={busy} onClick={onCreateAnother}>继续新建</button>}
            {versionSaved && onOpenEnvironment && <button type="button" disabled={busy} onClick={onOpenEnvironment}>搭建环境 →</button>}
          </div>
          <details className="card-asset-details"><summary>检查、文件与归一化</summary>
            <p>Blender {version.blender_version} · {version.operation}</p>
            <div className="card-asset-links"><a href={cardAssetFileUrl(asset.id,'blend',version.number)}>.blend</a><a href={cardAssetFileUrl(asset.id,'preview',version.number)}>GLB</a><a href={cardAssetFileUrl(asset.id,'fbx',version.number)}>FBX</a>{asset.source_path && <a href={cardAssetFileUrl(asset.id,'source')}>原文件</a>}</div>
            <div className="card-asset-normalize"><label>最大边（米）<input type="number" min="0.001" max="1000" step="0.1" value={target} disabled={busy} onChange={event=>setTargets(current=>({...current,[asset.id]:event.target.value}))}/></label>
              <button disabled={busy || !Number(target) || Number(target)<=0} onClick={()=>{setNotice(null);normalized.mutate({asset,target:Number(target)});}}>另存归一化版本</button></div>
            {asset.log_path && <p>日志：{asset.log_path}</p>}
          </details></>}
        {asset.error && <p role="alert">{asset.error}</p>}
      </article>;
    })}</div> : !liveUpdated.isPending && <p className="card-asset-empty">{source === 'create' ? '发送第一轮模型描述后，这里会出现 v1 的真实 Three.js 预览。' : '选择 GLB 或 FBX 后，这里显示检查结果。'}</p>}
    {source === 'create' && latestProposal && <details className="card-latest-plan"><summary>当前版本的结构化方案</summary><h3>{latestProposal.title}</h3><p>{latestProposal.summary}</p><small>{latestProposal.parts.length} 个原语 · {latestProposal.provider} / {latestProposal.model}</small></details>}
    {library.error && <p role="alert" className="card-asset-notice" data-kind="error">资产库读取失败：{library.error.message}</p>}
    <footer>{source === 'create' ? '每轮成功都追加版本；不会覆盖旧模型，也不会自动提交 Git。' : '导入保留原件；归一化会追加版本。'}</footer>
  </section>;
}
