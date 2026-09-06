import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { workspaceClient, type FolderProjectIdentityInspection } from '@sceneops/workspace-client';
import './workspace-projects.css';

export function WorkspaceProjects({ projectId, onSelect }: { projectId: string | null; onSelect(id: string | null): void }) {
  const cache = useQueryClient();
  const projects = useQuery({ queryKey: ['workspace-projects'], queryFn: workspaceClient.projects });
  const folderProjects = useQuery({ queryKey: ['workspace-folder-projects'], queryFn: workspaceClient.folderProjects });
  const [browsePath, setBrowsePath] = useState<string>();
  const [pathInput, setPathInput] = useState('');
  const [showHidden, setShowHidden] = useState(false);
  const folders = useQuery({ queryKey: ['workspace-folders', browsePath ?? 'home'], queryFn: () => workspaceClient.folders(browsePath) });
  const [name, setName] = useState('');
  const [folderName, setFolderName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [identityBusy, setIdentityBusy] = useState(false);
  const [inspection, setInspection] = useState<FolderProjectIdentityInspection | null>(null);
  const refreshProjects = async () => {
    await Promise.all([
      cache.invalidateQueries({ queryKey: ['workspace-projects'] }),
      cache.invalidateQueries({ queryKey: ['workspace-folder-projects'] }),
      cache.invalidateQueries({ queryKey: ['workspace-folders'] }),
    ]);
  };
  const inspectCurrentFolder = async () => {
    if (!folders.data) return;
    setIdentityBusy(true); setError('');
    try { setInspection(await workspaceClient.inspectFolderProject({path: folders.data.path})); }
    catch (e) { setInspection(null); setError(e instanceof Error ? e.message : String(e)); }
    finally { setIdentityBusy(false); }
  };
  const recoverCurrentFolder = async (resolution: 'restore' | 'move' | 'copy') => {
    if (!inspection) return;
    setIdentityBusy(true); setError('');
    try {
      const project = await workspaceClient.recoverFolderProject({path: inspection.path, resolution});
      await refreshProjects();
      setInspection(await workspaceClient.inspectFolderProject({path: inspection.path}));
      onSelect(project.project_id);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setIdentityBusy(false); }
  };
  return <section className="shell-tool-content workspace-folder-intake" aria-label="本地项目">
    <header className="workspace-projects-header"><h2>项目</h2><p>选择文件夹，开始协作。</p></header>
    {projects.isPending && <p role="status">正在读取本地项目…</p>}
    {projects.error && <p role="alert">{projects.error.message} <button onClick={() => void projects.refetch()}>重试</button></p>}
    {projects.data?.projects.length === 0 && <div className="workspace-projects-empty"><strong>空工作区</strong><span>先创建一个本地项目，再开始整理目标和生产计划。</span></div>}
    <details><summary>原有项目与独立对话</summary><div className="workspace-project-list"><button className={`workspace-project-card ${!projectId ? 'is-selected' : ''}`} onClick={() => onSelect(null)} aria-pressed={!projectId}><span><strong>未选择项目</strong><small>保留为独立对话，不附带项目上下文</small></span><b>{!projectId ? '当前' : '选择'}</b></button>
    {projects.data?.projects.filter(project => !folderProjects.data?.projects.some(folder => folder.project_id === project.project_id)).map(project => <button className={`workspace-project-card ${projectId === project.project_id ? 'is-selected' : ''}`} key={project.project_id} aria-pressed={projectId === project.project_id} onClick={() => onSelect(project.project_id)}><span><strong>{project.name}</strong><small>原有本地项目</small></span><b>{projectId === project.project_id ? '当前' : '选择'}</b></button>)}</div></details>
    <div className="workspace-project-create">
      <div><h3>最近项目</h3></div>
      {folderProjects.isPending && <p role="status">正在读取文件夹项目…</p>}
      {folderProjects.error && <p role="alert">{folderProjects.error.message} <button onClick={() => void folderProjects.refetch()}>重试</button></p>}
      {folderProjects.data?.projects.length === 0 && <p>尚未创建文件夹项目。</p>}
      <div className="workspace-project-list">
        {folderProjects.data?.projects.map(project => <button className={`workspace-project-card ${projectId === project.project_id ? 'is-selected' : ''}`} key={project.project_id} aria-pressed={projectId === project.project_id} disabled={project.root_available === false} onClick={() => onSelect(project.project_id)}><span><strong>{project.name}</strong><small>{project.root_path}</small>{project.root_available === false && <small>原登记目录不可用 · 请浏览移动后的目录并检查身份</small>}{project.project_kind === 'existing_unadopted' && <small>副本已登记 · 等待已有工程采用流程</small>}</span><b>{project.root_available === false ? '等待定位' : projectId === project.project_id ? '当前' : '重新打开'}</b></button>)}
      </div>
    </div>
    <form onSubmit={async event => {
      event.preventDefault();
      if (!folders.data) return;
      setBusy(true); setError('');
      try {
        const project = await workspaceClient.createFolderProject({ parent_path: folders.data.path, name: folderName.trim() });
        await refreshProjects();
        setFolderName(''); onSelect(project.project_id);
      } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
    }} className="workspace-project-create">
      <div><h3>新项目</h3><p>在所选位置创建新子目录，保留已有文件。</p></div>
      <label>跳转到文件夹<input value={pathInput} placeholder="输入绝对路径，或在下方浏览" onChange={e => setPathInput(e.target.value)} /></label><button type="button" disabled={!pathInput.trim()} onClick={() => setBrowsePath(pathInput.trim())}>打开路径</button>
      {folders.isPending && <p role="status">正在读取目录…</p>}
      {folders.error && <p role="alert">{folders.error.message} <button type="button" onClick={() => void folders.refetch()}>重试</button></p>}
      {folders.data && <div>
        <p><strong>当前父目录</strong><br/><small>{folders.data.path}</small></p>
        <button type="button" disabled={identityBusy} onClick={() => void inspectCurrentFolder()}>
          {identityBusy ? '检查中…' : '检查此文件夹中的 SceneOps 项目'}
        </button>
        {inspection?.path === folders.data.path && <div className="workspace-identity-review" role="status">
          <strong>{inspection.status === 'registered' ? '项目身份已登记' :
            inspection.status === 'recoverable' ? '发现可恢复项目' :
            inspection.status === 'move_candidate' ? '发现移动后的项目或副本' :
            inspection.status === 'identity_conflict' ? '发现重复项目身份' : '尚未采用的已有工程'}</strong>
          <p>{inspection.message}</p>
          {inspection.registered_root_path && inspection.registered_root_path !== inspection.path &&
            <small>原登记位置：{inspection.registered_root_path}</small>}
          <div className="workspace-identity-actions">
            {inspection.status === 'registered' && inspection.project_id &&
              <button type="button" onClick={() => onSelect(inspection.project_id!)}>打开已登记项目</button>}
            {(inspection.allowed_resolutions ?? []).includes('restore') &&
              <button type="button" disabled={identityBusy} onClick={() => void recoverCurrentFolder('restore')}>恢复本机登记</button>}
            {(inspection.allowed_resolutions ?? []).includes('move') &&
              <button type="button" disabled={identityBusy} onClick={() => void recoverCurrentFolder('move')}>确认是移动后的原项目</button>}
            {(inspection.allowed_resolutions ?? []).includes('copy') &&
              <button type="button" disabled={identityBusy} onClick={() => void recoverCurrentFolder('copy')}>作为副本登记并分配新 ID</button>}
          </div>
        </div>}
        <details><summary>浏览文件夹</summary>{folders.data.parent_path && <button type="button" onClick={() => setBrowsePath(folders.data?.parent_path ?? undefined)}>返回上一级</button>}
        <label><input type="checkbox" checked={showHidden} onChange={e => setShowHidden(e.target.checked)} />显示隐藏目录</label>
        <div className="workspace-project-list" aria-label="子目录" style={{maxHeight:220, overflow:'auto'}}>
          {folders.data.entries.filter(entry => showHidden || !entry.name.startsWith('.')).map(entry => <button type="button" className="workspace-project-card" key={entry.path} disabled={!entry.selectable} onClick={() => { setBrowsePath(entry.path); setInspection(null); }}><span><strong>{entry.name}</strong></span><b>{entry.selectable ? '打开' : '符号链接不可选'}</b></button>)}
        </div></details>
      </div>}
      <label>新项目目录名称 <input required maxLength={160} value={folderName} placeholder="例如：归途" onChange={e => setFolderName(e.target.value)} /></label>
      <p>协作 · 单人 + AI</p>
      <button disabled={busy || !folderName.trim() || !folders.data || folders.isFetching}>{busy ? '创建中…' : '创建文件夹项目'}</button>
    </form>
    <details><summary>高级：创建不绑定文件夹的旧版项目</summary><form onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError('');
      try { const project = await workspaceClient.create({ name: name.trim() }); await cache.invalidateQueries({ queryKey: ['workspace-projects'] }); setName(''); onSelect(project.project_id); }
      catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
    }} className="workspace-project-create"><div><span className="tool-kicker">NEW LOCAL PROJECT</span><h3>新建项目</h3><p>此入口保留旧版流程，不进入新策划旅程。</p></div><label>项目名称 <input required maxLength={160} value={name} placeholder="例如：归途" onChange={e => setName(e.target.value)} /></label><button disabled={busy || !name.trim()}>{busy ? '创建中…' : '创建空项目'}</button></form></details>
    {error && <p role="alert">{error}</p>}
  </section>;
}
