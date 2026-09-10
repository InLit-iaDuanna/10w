import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { GltfPreview } from '@sceneops/scene-viewer/react';
import { builtinAssets, type BuiltinAsset } from './builtin-client';
import './builtin-assets.css';

const categories = [{id:'scene',label:'完整场景'}, {id:'prop',label:'建筑与物件'}, {id:'character',label:'角色'}] as const;

export function BuiltinAssetLibrary({projectId, suspended = false, onOpenProjects, onOpenEnvironment}: {
  projectId: string | null; suspended?: boolean;
  onOpenProjects: () => void; onOpenEnvironment: () => void;
}) {
  const query = useQuery({queryKey:['builtin-assets'],queryFn:({signal})=>builtinAssets.list(signal),retry:false,enabled:!suspended});
  const cache = useQueryClient();
  const [category,setCategory] = useState<BuiltinAsset['kind']>('scene');
  const [selectedId,setSelectedId] = useState<string|null>(null);
  const [view3d,setView3d] = useState(true);
  const [notice,setNotice] = useState('');
  const [search,setSearch] = useState('');
  const [pack,setPack] = useState('');
  const [style,setStyle] = useState('');
  const [promptStyle,setPromptStyle] = useState('低多边形');
  const [artStyle,setArtStyle] = useState('');
  const [visibleCount,setVisibleCount] = useState(60);
  const styles = [...new Set(query.data?.entries.filter(entry=>entry.kind===category && (!pack || entry.pack_id===pack)).map(entry=>entry.category) ?? [])];
  const normalizedSearch = search.trim().toLocaleLowerCase();
  const entries = query.data?.entries.filter(entry=>entry.kind===category && (!pack || entry.pack_id===pack) && (!artStyle || entry.art_style===artStyle || (artStyle==='像素' && !!entry.sprite_url)) && (!style || entry.category===style) && [entry.label,entry.category,entry.asset_category,entry.description,entry.pack_title,...(entry.tags ?? [])].join(' ').toLocaleLowerCase().includes(normalizedSearch)) ?? [];
  const visibleEntries = entries.slice(0,visibleCount);
  const selected = entries.find(entry=>entry.asset_id===selectedId);
  const selectedPack = query.data?.packs.find(item=>item.pack_id===selected?.pack_id);
  useEffect(()=>setVisibleCount(60),[category,pack,style,artStyle,search]);
  const adopt = useMutation({mutationFn:async (assetId:string) => {
    if (!projectId) throw new Error('请先选择一个游戏项目。');
    return builtinAssets.adopt(assetId,projectId);
  },onSuccess:async result=>{
    setNotice(`${result.entry.title}已加入项目资产库，可以在环境场景中摆放。`);
    await cache.invalidateQueries({queryKey:['project-assets',projectId]});
  }});
  if (query.isPending) return <p role="status">正在读取内置资产…</p>;
  if (query.error) return <p role="alert">内置资产读取失败：{query.error.message} <button onClick={()=>void query.refetch()}>重试</button></p>;
  return <section className="builtin-assets" aria-label="内置场景与资产">
    <div className="builtin-browse" hidden={!!selected}>
    <header className="builtin-heading"><div><span className="builtin-eyebrow">SCENEOPS ORIGINALS · {query.data.packs.length} 个资产包</span>
      <h2>内置资产</h2><p>挑选场景、建筑、装备与角色，加入项目即可使用。</p></div><span className="builtin-license">{query.data.license}</span></header>
    <nav className="builtin-filters" aria-label="资产类型">{categories.map(item=><button key={item.id} aria-pressed={category===item.id}
      onClick={()=>{setCategory(item.id);setStyle('');setSelectedId(null);setView3d(true);}}>{item.label}<span>{query.data.entries.filter(entry=>entry.kind===item.id && (!pack || entry.pack_id===pack)).length}</span></button>)}</nav>
    <label className="builtin-search"><span className="builtin-search-label">搜索资产</span>
      <input aria-label="搜索资产" type="search" value={search} placeholder="例如：科幻、经营、竞速、地牢" onChange={event=>{setSearch(event.target.value);setSelectedId(null);setView3d(true);}} />
      
    </label>
    <div className="builtin-discovery">
      <label>资产包 <select value={pack} onChange={event=>{setPack(event.target.value);setStyle('');setSelectedId(null);setView3d(true);}}>
        <option value="">全部资产包</option>{query.data.packs.map(value=><option key={value.pack_id} value={value.pack_id}>{value.title} · v{value.version}</option>)}
      </select></label>
      <label>美术形式 <select value={artStyle} onChange={event=>{setArtStyle(event.target.value);setStyle('');if(event.target.value==='像素')setCategory('character');setSelectedId(null);setView3d(true);}}>
        <option value="">全部形式</option>{['低多边形','体素','像素','纸艺','PBR材质','黏土','搪瓷'].map(value=><option key={value}>{value}</option>)}
      </select></label>
      <label>场景主题 <select value={style} onChange={event=>{setStyle(event.target.value);setSelectedId(null);setView3d(true);}}>
        <option value="">全部主题</option>{styles.map(value=><option key={value} value={value}>{value}</option>)}
      </select></label>
      <nav aria-label="常用游戏与应用方向">{['经营','探索','解谜','生存','教育','竞速','平台跳跃','策略'].map(value=><button key={value}
        aria-pressed={search===value} onClick={()=>{setSearch(search===value?'':value);setStyle('');setSelectedId(null);setView3d(true);}}>{value}</button>)}</nav>
      {(search || pack || style || artStyle) && <button onClick={()=>{setSearch('');setPack('');setStyle('');setArtStyle('');setSelectedId(null);setView3d(true);}}>清除筛选</button>}
    </div>
    </div>
    {selected && <div className="builtin-workspace">
      <header className="builtin-selected-header">
        <div><button className="builtin-back" onClick={()=>{setSelectedId(null);setView3d(true);}}>← 资产库</button>
          <div className="builtin-selected-title"><h2>{selected.label}</h2><span>{selected.pack_title} · v{selected.pack_version}</span><span>{selected.asset_category || selected.category}</span>{!!selected.animations?.length && <span>{selected.animations.length} 个动作</span>}</div>
          <p>{selected.kind==='character'?'切换动作，拖动进度，边看边调整。':'旋转检查模型，调整视角与光照效果。'}</p>
        </div>
        <div className="builtin-preview-mode" aria-label="预览模式"><button aria-pressed={view3d} onClick={()=>setView3d(true)}>实时 3D</button><button aria-pressed={!view3d} onClick={()=>setView3d(false)}>效果图</button></div>
      </header>
      <div hidden={!view3d}><GltfPreview key={selected.asset_url} url={selected.asset_url} label={`${selected.label} 3D 预览`} suspended={suspended || !view3d} studio/></div>
      {!view3d && <div className="builtin-photo-preview"><img src={selected.preview_url} alt={selected.preview_source==='scene'?`${selected.label} 所属场景参考图`:selected.label}/><button onClick={()=>setView3d(true)}>打开实时预览 →</button></div>}
      {selected.preview_source==='scene' && !view3d && <p className="builtin-preview-note">此单体暂未附独立效果图，当前展示所属场景参考；实时 3D 为该资产本体。</p>}
      <div className="builtin-asset-actions"><div><strong>{selected.dimensions_m.map(value=>value.toFixed(1)).join(' × ')} m</strong><span>{selected.rig?.status==='skinned'?(selected.rig?.shared_skeleton===true?'已绑定 · 共用骨架':'已绑定骨骼'):'独立可复用资产'} · GLB · {selected.license}</span></div>
        <a href={selected.asset_url} download={`${selected.label}.glb`}>下载模型 ↗</a>
        {projectId ? <button className="builtin-adopt" disabled={adopt.isPending} onClick={()=>{setNotice('');adopt.mutate(selected.asset_id);}}>{adopt.isPending?'正在加入…':'加入项目资产库'}</button>
          : <button className="builtin-adopt" onClick={onOpenProjects}>选择项目后使用</button>}
      </div>
      <details className="builtin-asset-info"><summary>资产说明与技术资料</summary><p>{selected.description}</p>
        <dl className="builtin-tech-grid">
          <div><dt>来源</dt><dd>{selected.pack_title} · v{selected.pack_version} · {selected.license}</dd></div>
          <div><dt>几何</dt><dd>{selected.triangle_count?.toLocaleString() ?? '未记录'} 三角面</dd></div>
          <div><dt>LOD</dt><dd>{selected.lods?.length ? `${selected.lods.length} 级` : '仅原始模型'}</dd></div>
          <div><dt>UV / 材质</dt><dd>{selected.uv_sets?.length ? `${selected.uv_sets.join('、')} · ${selected.material_channels?.length ?? 0} 通道` : '随 GLB'}</dd></div>
          {selected.source_texture_resolution && <div><dt>源纹理</dt><dd>{selected.source_texture_resolution.join(' × ')} px</dd></div>}
          <div><dt>物理绑定</dt><dd>{selected.physics_url?'已提供配置':'未提供'}</dd></div>
        </dl>
        {!!selected.lods?.length && <div className="builtin-reuse-links">{selected.lods.map(lod=><a key={lod.level} href={lod.asset_url} download>{`下载 LOD${lod.level}${lod.triangle_count == null?'':` · ${lod.triangle_count.toLocaleString()} 面`} ↗`}</a>)}</div>}
        {selected.physics_url && <a href={selected.physics_url} download={`${selected.asset_id}.physics.json`}>下载物理绑定 ↗</a>}
        {selected.scene_url && <a href={selected.scene_url} download={`${selected.asset_id}.scene.json`}>下载场景定义 ↗</a>}
        {selectedPack?.catalog_url && <a href={selectedPack.catalog_url} download={`${selected.pack_id}-catalog.json`}>下载素材包原始清单 ↗</a>}
        {selected.rig_source_url && <a href={selected.rig_source_url} download>下载可编辑骨骼源文件（Blender） ↗</a>}
      </details>
    </div>}
    {selected && (selected.shared_motion_url || selected.reusable_asset_ids?.length || selected.sprite_url || selected.generation_prompt) ? <section className="builtin-reuse" aria-label="复用与生成参考">
      {selected.shared_motion_url && <div><h3>同系列角色共用骨架与动作</h3><p>这些角色使用同一套骨架，可直接复用四段动画。新角色从共用骨架制作，并重新绑定自己的网格权重。</p>
        <div className="builtin-reuse-links"><a href={selected.shared_motion_url} download>下载共用动作包 ↗</a>
        {selected.rig_template_url && <a href={selected.rig_template_url} download>下载共用骨架模板 ↗</a>}</div></div>}
      {!!selected.reusable_asset_ids?.length && <div><h3>关联的可复用资产与场景</h3><div className="builtin-reuse-links">
        {selected.reusable_asset_ids.map(id=>query.data.entries.find(entry=>entry.asset_id===id)).filter((entry):entry is BuiltinAsset=>!!entry).map(entry=><button key={entry.asset_id} onClick={()=>{
          setCategory(entry.kind);setSearch('');setPack(entry.pack_id);setStyle('');setArtStyle('');setSelectedId(entry.asset_id);setView3d(true);
        }}>{entry.label}</button>)}
      </div></div>}
      {selected.sprite_url && <div className="builtin-pixel"><img src={selected.sprite_url} alt={`${selected.label} 四方向像素步行图集`} />
        <div><h3>二维像素角色图集</h3><p>32 × 48 像素／帧，4 方向 × 4 帧，6 FPS。透明背景，最近邻缩放；脚点为 (16,46)。</p>
        <a href={selected.sprite_url} download={`${selected.label}-sprites.png`}>下载 PNG 图集 ↗</a></div></div>}
      {selected.generation_prompt && <details className="builtin-prompts"><summary>给其他 agent 的生成提示词</summary>
        <label>目标风格 <select value={promptStyle} onChange={event=>setPromptStyle(event.target.value)}>
          {Object.keys(selected.style_prompts ?? {}).map(value=><option key={value}>{value}</option>)}
        </select></label>
        <p>切换目标风格可获取对应的生成要求。写实与手绘指南不代表当前已交付完整的该风格套装。</p>
        <textarea readOnly aria-label="资产生成提示词" value={selected.style_prompts?.[promptStyle] ?? selected.generation_prompt} />
        <button onClick={()=>{void navigator.clipboard.writeText(selected.style_prompts?.[promptStyle] ?? selected.generation_prompt ?? '').then(()=>setNotice('生成提示词已复制。'),()=>setNotice('未能访问剪贴板，请从文本框选中并复制提示词。'));}}>复制提示词</button>
      </details>}
    </section> : null}
    {adopt.error && <p role="alert">{adopt.error.message}</p>}
    {notice && <div className="builtin-notice" role="status">{notice}<button onClick={onOpenEnvironment}>打开环境场景</button></div>}
    {!selected && <div className="builtin-results"><span role="status">{entries.length} 项资产</span><span>选择资产查看详情</span></div>}
    <div hidden={!!selected} className="builtin-grid" aria-label="可复用资产">{visibleEntries.map(entry=><button className="builtin-card" key={entry.asset_id}
      aria-pressed={selected?.asset_id===entry.asset_id} onClick={()=>{setSelectedId(entry.asset_id);setView3d(true);}}>
      <img src={entry.preview_url} alt="" loading="lazy"/><span><strong>{entry.label}</strong><small>{entry.asset_category || entry.category} · {entry.category}</small></span>
    </button>)}</div>
    {!selected && visibleEntries.length < entries.length && <button className="builtin-load-more" onClick={()=>setVisibleCount(count=>count+60)}>加载更多（还有 {entries.length-visibleEntries.length} 项）</button>}
    {!entries.length && <p>没有匹配的资产，请尝试其他关键词或分类。</p>}
  </section>;
}
