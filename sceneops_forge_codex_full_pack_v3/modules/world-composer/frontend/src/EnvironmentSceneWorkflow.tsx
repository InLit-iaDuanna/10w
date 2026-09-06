import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { EnvironmentScenePreview } from './EnvironmentScenePreview.tsx';
import {
  environmentAssetFileUrl,
  environmentAssetsKey,
  environmentSceneClient,
  environmentSceneKey,
  type EnvironmentObject,
  type EnvironmentScene,
  type ProjectAssetEntry,
} from './environment-client.ts';
import './environment-scene.css';

type TransformDraft = {x:string;y:string;z:string;rotation:string;scale:string};
type AssetSource = 'import' | 'create';
const SCENE_SHARE_KEY = 'sceneops.environment.scene-share.v1';

function clampSceneShare(value: number) {
  return Math.min(76, Math.max(28, value));
}

function AssetGlyph() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></svg>;
}

function currentVersion(asset: ProjectAssetEntry, selected: number | undefined) {
  return asset.versions.find(version => version.source_version === (selected ?? asset.current_version))
    ?? asset.versions.at(-1)!;
}

export function EnvironmentSceneWorkflow({projectId, aiBusy = false, onCreateAsset, onImportAsset}: {
  projectId: string; aiBusy?: boolean; onCreateAsset?: (source: AssetSource) => void;
  onImportAsset?: (file: File) => Promise<ProjectAssetEntry>;
}) {
  const cache = useQueryClient();
  const splitRoot = useRef<HTMLElement>(null);
  const assetPane = useRef<HTMLElement>(null);
  const draggingSplit = useRef(false);
  const dragDepth = useRef(0);
  const sceneKey = environmentSceneKey(projectId);
  const assetsKey = environmentAssetsKey(projectId);
  const sceneQuery = useQuery({queryKey:sceneKey, queryFn:({signal}) => environmentSceneClient.get(projectId, signal), retry:false});
  const assetsQuery = useQuery({queryKey:assetsKey, queryFn:({signal}) => environmentSceneClient.assets(projectId, signal), retry:false});
  const [sceneShare, setSceneShare] = useState(() => clampSceneShare(Number(localStorage.getItem(SCENE_SHARE_KEY)) || 62));
  const [selectedSceneId, setSelectedSceneId] = useState<string|null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string|null>(null);
  const [selectedAssetVersions, setSelectedAssetVersions] = useState<Record<string,number>>({});
  const [assetName, setAssetName] = useState('');
  const [addingAsset, setAddingAsset] = useState(false);
  const [error, setError] = useState('');
  const [dropActive, setDropActive] = useState(false);
  const [dropNotice, setDropNotice] = useState('');
  const [draft, setDraft] = useState<TransformDraft>({x:'0',y:'0',z:'0',rotation:'0',scale:'1'});
  const scene = sceneQuery.data;
  const objects = scene?.objects ?? [];
  const assets = assetsQuery.data ?? [];
  const selectedSceneObject = objects.find(item => item.id === selectedSceneId) ?? null;
  const selectedSceneAsset = selectedSceneObject ? assets.find(item => item.id === selectedSceneObject.asset_id) : null;
  const selectedAsset = assets.find(item => item.id === selectedAssetId) ?? null;
  const assetVersion = selectedAsset ? currentVersion(selectedAsset, selectedAssetVersions[selectedAsset.id]) : null;

  const updateScene = (value: EnvironmentScene) => {
    cache.setQueryData(sceneKey, value);
    const nextObjects = value.objects ?? [];
    if (selectedSceneId && !nextObjects.some(item => item.id === selectedSceneId)) {
      setSelectedSceneId(null);
    }
  };
  const placed = useMutation({mutationFn:({assetId,version}:{assetId:string;version:number}) => {
    if (!scene) throw new Error('场景尚未读取。');
    return environmentSceneClient.place(projectId, {expected_version:scene.version,asset_id:assetId,asset_version:version});
  }, onSuccess:value => {
    updateScene(value);
    setSelectedSceneId(null);
    setSelectedAssetId(null);
    setError('');
  }, onError:error => setError(error.message)});
  const dropped = useMutation({mutationFn:async (files:File[]) => {
    if (!onImportAsset) throw new Error('当前宿主没有连接模型导入服务。');
    const unsupported = files.find(file => !/\.(glb|fbx)$/i.test(file.name));
    if (unsupported) throw new Error(`不支持 ${unsupported.name}；请拖入 GLB 或 FBX 文件。`);
    let nextScene = await environmentSceneClient.get(projectId);
    for (const file of files) {
      const entry = await onImportAsset(file);
      cache.setQueryData<ProjectAssetEntry[]>(assetsKey, current => [entry, ...(current ?? []).filter(item => item.id !== entry.id)]);
      const version = currentVersion(entry, undefined);
      nextScene = await environmentSceneClient.place(projectId, {expected_version:nextScene.version,
        asset_id:entry.id,asset_version:version.source_version});
    }
    return {scene:nextScene,count:files.length};
  }, onSuccess:result => {
    updateScene(result.scene);
    setSelectedAssetId(null);
    setDropNotice(`已导入 ${result.count} 个模型并加入场景。`);
    setError('');
  }, onError:error => {setDropNotice('');setError(error.message);}});
  const transformed = useMutation({mutationFn:() => {
    if (!scene || !selectedSceneObject) throw new Error('请先选择一个场景对象。');
    const values = [draft.x,draft.y,draft.z,draft.rotation,draft.scale].map(Number);
    if (values.some(value => !Number.isFinite(value)) || values[4]! <= .01) throw new Error('位置、旋转和缩放必须是有效数字。');
    return environmentSceneClient.transform(projectId, selectedSceneObject.id, {expected_version:scene.version,transform:{
      position_m:[values[0]!,values[1]!,values[2]!],rotation_y_deg:values[3]!,scale:values[4]!,
    }});
  }, onSuccess:value => {updateScene(value);setError('');}, onError:error => setError(error.message)});
  const removed = useMutation({mutationFn:(object:EnvironmentObject) => {
    if (!scene) throw new Error('场景尚未读取。');
    return environmentSceneClient.remove(projectId, object.id, scene.version);
  }, onSuccess:value => {updateScene(value);setError('');}, onError:error => setError(error.message)});
  const renamed = useMutation({mutationFn:() => {
    if (!selectedAsset) throw new Error('资产尚未读取。');
    return environmentSceneClient.renameAsset(projectId, selectedAsset.id, assetName.trim(), selectedAsset.updated_at ?? '');
  }, onSuccess:value => {
    cache.setQueryData<ProjectAssetEntry[]>(assetsKey, current => (current ?? []).map(item => item.id === value.id ? value : item));
    setAssetName(value.title);
    setError('');
  }, onError:error => setError(error.message)});
  const onSceneSelect = useCallback((id:string|null) => {
    setSelectedAssetId(null);
    setAddingAsset(false);
    setSelectedSceneId(id);
  }, []);

  useEffect(() => {
    setSelectedSceneId(null);
    setSelectedAssetId(null);
    setAddingAsset(false);
  }, [projectId]);
  useEffect(() => {
    setDropActive(false);
    setDropNotice('');
    dragDepth.current = 0;
  }, [projectId]);
  useEffect(() => {
    if (!selectedSceneObject) return;
    setDraft({x:String(selectedSceneObject.transform.position_m[0]),y:String(selectedSceneObject.transform.position_m[1]),
      z:String(selectedSceneObject.transform.position_m[2]),rotation:String(selectedSceneObject.transform.rotation_y_deg),
      scale:String(selectedSceneObject.transform.scale)});
  }, [selectedSceneObject]);
  useEffect(() => { setAssetName(selectedAsset?.title ?? ''); }, [selectedAsset?.id, selectedAsset?.title]);
  useEffect(() => {
    if (selectedAssetId && !assets.some(item => item.id === selectedAssetId)) setSelectedAssetId(null);
  }, [assets, selectedAssetId]);
  useEffect(() => { assetPane.current?.scrollTo({top:0,behavior:'auto'}); }, [selectedSceneId, selectedAssetId, addingAsset]);
  useEffect(() => { localStorage.setItem(SCENE_SHARE_KEY, String(sceneShare)); }, [sceneShare]);

  if (sceneQuery.isPending || assetsQuery.isPending) return <p role="status" className="environment-loading">读取项目资产库与场景…</p>;
  if (sceneQuery.error || assetsQuery.error || !scene) return <p role="alert" className="environment-error">{(sceneQuery.error ?? assetsQuery.error)?.message ?? '场景读取失败'} <button onClick={() => {void sceneQuery.refetch();void assetsQuery.refetch();}}>重试</button></p>;
  const busy = placed.isPending || dropped.isPending || transformed.isPending || removed.isPending || renamed.isPending || aiBusy;
  const profile = scene.scale_profile ?? {unit:'meter' as const,up_axis:'Y' as const,handedness:'right' as const,
    grid_step_m:1,reference_human_height_m:1.8,default_object_spacing_m:3};
  const beginAsset = (source: AssetSource) => {
    setAddingAsset(false);
    onCreateAsset?.(source);
  };
  const resizeScene = (clientY: number) => {
    const bounds = splitRoot.current?.getBoundingClientRect();
    if (!bounds) return;
    setSceneShare(clampSceneShare(((clientY - bounds.top) / bounds.height) * 100));
  };
  const splitStyle = {'--environment-scene-share': `${sceneShare}%`} as CSSProperties;

  return <section ref={splitRoot} className="environment-workflow" aria-label="环境场景搭建" style={splitStyle}>
    <section className="environment-scene-card" aria-label="世界场景预览">
      <div className="environment-status"><span>场景 v{scene.version}</span><strong>{objects.length} 个对象</strong><small>{aiBusy ? 'AI 搭建中 · ' : ''}米 · Y↑ · {profile.grid_step_m}m 网格</small></div>
      <div className={`environment-scene-dropzone${dropActive ? ' is-dragging' : ''}${dropped.isPending ? ' is-importing' : ''}`}
        onDragEnter={event => {if (!onImportAsset || !Array.from(event.dataTransfer.types).includes('Files')) return;event.preventDefault();if (!busy) {dragDepth.current += 1;setDropActive(true);}}}
        onDragOver={event => {if (!onImportAsset || !Array.from(event.dataTransfer.types).includes('Files')) return;event.preventDefault();event.dataTransfer.dropEffect = busy ? 'none' : 'copy';}}
        onDragLeave={() => {dragDepth.current = Math.max(0, dragDepth.current - 1);if (!dragDepth.current) setDropActive(false);}}
        onDrop={event => {if (!onImportAsset) return;event.preventDefault();dragDepth.current = 0;setDropActive(false);setDropNotice('');if (busy) {setError('当前场景正在处理，请完成后再导入。');return;}const files=Array.from(event.dataTransfer.files);if (files.length) dropped.mutate(files);}}>
        <EnvironmentScenePreview objects={objects} selectedId={selectedSceneId} onSelect={onSceneSelect}/>
        {onImportAsset && <div className="environment-drop-hint" aria-live="polite">{dropped.isPending ? '正在导入、检查并加入场景…' : dropActive ? '松开以导入并加入场景' : '拖入 GLB / FBX 直接导入'}</div>}
      </div>
      {dropNotice && <p role="status" className="environment-import-notice">{dropNotice}</p>}
    </section>
    <div className="environment-splitter" role="separator" aria-label="调整场景与项目资产高度" aria-orientation="horizontal"
      aria-valuemin={28} aria-valuemax={76} aria-valuenow={Math.round(sceneShare)} tabIndex={0}
      onPointerDown={event => {draggingSplit.current = true;event.currentTarget.setPointerCapture(event.pointerId);resizeScene(event.clientY);}}
      onPointerMove={event => {if (draggingSplit.current) resizeScene(event.clientY);}}
      onPointerUp={event => {draggingSplit.current = false;event.currentTarget.releasePointerCapture(event.pointerId);}}
      onPointerCancel={() => {draggingSplit.current = false;}}
      onKeyDown={event => {if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') return;event.preventDefault();setSceneShare(value => clampSceneShare(value + (event.key === 'ArrowUp' ? -4 : 4)));}}><span/></div>
    <section ref={assetPane} className="environment-assets-card" aria-label={selectedSceneObject ? '已选模型信息' : '项目资产'}>
      {error && <p role="alert" className="environment-error">{error}</p>}
      {addingAsset && onCreateAsset && <section className="environment-new-asset" aria-label="添加资产方式"><div><strong>添加一个资产</strong><small>只带入项目背景和世界尺度，不带入上一个资产的对话。</small></div><div><button onClick={() => beginAsset('import')}>导入 GLB / FBX</button><button className="primary" onClick={() => beginAsset('create')}>新建模型</button><button aria-label="取消添加资产" onClick={() => setAddingAsset(false)}>取消</button></div></section>}
      {selectedSceneObject ? <section className="environment-inspector" aria-label={`${selectedSceneAsset?.title ?? selectedSceneObject.title} 场景模型信息`}>
        <header><div><button type="button" className="scene-back" onClick={() => setSelectedSceneId(null)}>← 项目资产</button><strong>{selectedSceneAsset?.title ?? selectedSceneObject.title}</strong><small>已选模型 · 场景实例 · {selectedSceneObject.id}</small></div><button disabled={busy} onClick={() => removed.mutate(selectedSceneObject)}>移出场景</button></header>
        <div className="environment-transform-grid">
          {([['x','X'],['y','Y'],['z','Z'],['rotation','旋转 Y°'],['scale','缩放']] as const).map(([key,label]) => <label key={key}>{label}<input type="number" step={key === 'rotation' ? 5 : .1} value={draft[key]} disabled={busy} onChange={event => setDraft(current => ({...current,[key]:event.target.value}))}/></label>)}
        </div><button className="primary" disabled={busy} onClick={() => transformed.mutate()}>应用变换</button>
      </section> : selectedAsset && assetVersion ? <section className="environment-asset-editor" aria-label={`${selectedAsset.title} 资产编辑`}>
        <header><button type="button" className="asset-back" onClick={() => setSelectedAssetId(null)}>← 资产库</button><span>v{assetVersion.source_version}</span></header>
        <div className="asset-editor-body">
          <form className="asset-name-editor" onSubmit={event => {event.preventDefault();renamed.mutate();}}>
            <label>名称<input aria-label="资产名称" value={assetName} maxLength={24} disabled={busy} onChange={event => setAssetName(event.target.value)}/></label>
            <button type="submit" disabled={busy || !assetName.trim() || assetName.trim() === selectedAsset.title}>保存</button>
          </form>
          <div className="asset-scale-context"><strong>世界尺度</strong><span>米制 · Y 轴向上 · 人物参考 {profile.reference_human_height_m}m</span><small>新建和导入归一化都使用这份项目背景。</small></div>
          <div className="asset-version-picker" aria-label="资产版本">{selectedAsset.versions.map(version => <button type="button" key={version.source_version}
            aria-pressed={version.source_version === assetVersion.source_version}
            onClick={() => setSelectedAssetVersions(current => ({...current,[selectedAsset.id]:version.source_version}))}>v{version.source_version}</button>)}</div>
          <dl className="asset-metrics"><div><dt>尺寸</dt><dd>{assetVersion.dimensions_m.map(value => Number(value.toFixed(2))).join(' × ')} m</dd></div><div><dt>几何</dt><dd>{assetVersion.vertex_count} 顶点 · {assetVersion.triangle_count} 面</dd></div><div><dt>来源</dt><dd>{selectedAsset.source_type === 'generated' ? 'AI / Blender 新建' : '文件导入'}</dd></div></dl>
          <div className="asset-file-links"><a href={environmentAssetFileUrl(selectedAsset.source_asset_id,'blend',assetVersion.source_version)}>.blend</a><a href={environmentAssetFileUrl(selectedAsset.source_asset_id,'preview',assetVersion.source_version)}>GLB</a><a href={environmentAssetFileUrl(selectedAsset.source_asset_id,'fbx',assetVersion.source_version)}>FBX</a></div>
          {selectedAsset.source_title && selectedAsset.source_title !== selectedAsset.title && <details className="asset-source-title"><summary>原始生成说明</summary><p>{selectedAsset.source_title}</p></details>}
          <div className="asset-editor-actions"><button type="button" className="primary" disabled={busy} onClick={() => placed.mutate({assetId:selectedAsset.id,version:assetVersion.source_version})}>加入场景</button><button type="button" onClick={() => setAddingAsset(value => !value)}>＋ 添加资产</button></div>
        </div>
      </section> : <>
        <div className="environment-library-heading"><div><strong>项目资产</strong><small>{assets.length ? `${assets.length} 个资产 · 点击进入编辑` : '资产库为空'}</small></div>{onCreateAsset && <button onClick={() => setAddingAsset(value => !value)}>＋ 添加资产</button>}</div>
        <div className="environment-library" role="list" aria-label="项目资产库">
          {assets.map(asset => { const version = currentVersion(asset, undefined); return <button type="button" role="listitem" className="environment-asset-card" key={asset.id} onClick={() => {setSelectedSceneId(null);setSelectedAssetId(asset.id);setAddingAsset(false);}}>
            <span className="asset-card-icon"><AssetGlyph/></span><strong>{asset.title}</strong><small>v{asset.current_version} · {Math.max(...version.dimensions_m).toFixed(1)}m</small>
          </button>;})}
          {!assets.length && <p>先添加一个资产，导入或新建都会开启独立流程。</p>}
        </div>
      </>}
    </section>
  </section>;
}
