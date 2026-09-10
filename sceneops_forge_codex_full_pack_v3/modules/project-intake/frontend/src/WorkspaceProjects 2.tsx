import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { workspaceClient, type FolderEntry, type FolderProject, type FolderProjectIdentityInspection, type Project } from '@sceneops/workspace-client';
import './workspace-projects.css';

type FolderBrowserMode = 'create' | 'existing';

function FolderIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M3.5 7.5a2 2 0 0 1 2-2h4.2l2 2h6.8a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2Z" /></svg>;
}

function CloseIcon() {
  return <svg aria-hidden="true" viewBox="0 0 20 20"><path d="m5 5 10 10M15 5 5 15" /></svg>;
}

function inspectionTitle(inspection: FolderProjectIdentityInspection) {
  if (inspection.status === 'registered') return '项目已在 SceneOps 中登记';
  if (inspection.status === 'recoverable') return '发现可恢复项目';
  if (inspection.status === 'move_candidate') return '发现移动后的项目或副本';
  if (inspection.status === 'identity_conflict') return '发现重复项目身份';
  return '这个文件夹尚未采用';
}

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
  const [createOpen, setCreateOpen] = useState(false);
  const [folderBrowserMode, setFolderBrowserMode] = useState<FolderBrowserMode | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [deletingProjectId, setDeletingProjectId] = useState<string | null>(null);
  const [identityBusy, setIdentityBusy] = useState(false);
  const [inspection, setInspection] = useState<FolderProjectIdentityInspection | null>(null);

  const refreshProjects = async () => {
    await Promise.all([
      cache.invalidateQueries({ queryKey: ['workspace-projects'] }),
      cache.invalidateQueries({ queryKey: ['workspace-folder-projects'] }),
      cache.invalidateQueries({ queryKey: ['workspace-folders'] }),
    ]);
  };

  const showFolderBrowser = (mode: FolderBrowserMode) => {
    setError('');
    setInspection(null);
    setPathInput(folders.data?.path ?? browsePath ?? '');
    setFolderBrowserMode(mode);
  };

  const inspectAndOpenCurrentFolder = async () => {
    if (!folders.data) return;
    setIdentityBusy(true);
    setError('');
    try {
      const result = await workspaceClient.inspectFolderProject({ path: folders.data.path });
      setInspection(result);
      if (result.status === 'registered' && result.project_id) {
        onSelect(result.project_id);
        setFolderBrowserMode(null);
      }
    } catch (e) {
      setInspection(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIdentityBusy(false);
    }
  };

  const recoverCurrentFolder = async (resolution: 'restore' | 'move' | 'copy') => {
    if (!inspection) return;
    setIdentityBusy(true);
    setError('');
    try {
      const project = await workspaceClient.recoverFolderProject({ path: inspection.path, resolution });
      await refreshProjects();
      onSelect(project.project_id);
      setFolderBrowserMode(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setIdentityBusy(false);
    }
  };

  const closeCreate = () => {
    setCreateOpen(false);
    setError('');
  };

  const forgetFolderProject = async (project: FolderProject) => {
    if (!window.confirm(`从最近项目中移除“${project.name}”？\n\n项目文件夹和 Git 历史不会被删除，以后可通过“打开项目”重新登记。`)) return;
    setDeletingProjectId(project.project_id);
    setError('');
    try {
      await workspaceClient.forgetFolderProject(project.project_id);
      await refreshProjects();
      if (projectId === project.project_id) onSelect(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDeletingProjectId(null);
    }
  };

  return <section className="shell-tool-content workspace-folder-intake" aria-label="本地项目">
    <header className="workspace-projects-header workspace-projects-toolbar">
      <div><span className="workspace-projects-kicker">YOUR CREATIVE SPACE</span><h2>项目工作室</h2><p>每个游戏使用独立文件夹和 Git 历史。</p></div>
      <div className="workspace-projects-toolbar-actions">
        <button className="workspace-secondary-action" onClick={() => showFolderBrowser('existing')}><FolderIcon />打开项目</button>
        <button className="workspace-primary-action" onClick={() => { setError(''); setCreateOpen(true); }}>＋ 新建项目</button>
      </div>
    </header>

    {projects.isPending && <p role="status">正在读取本地项目…</p>}
    {projects.error && <p role="alert">{projects.error.message} <button onClick={() => void projects.refetch()}>重试</button></p>}
    {folderProjects.isPending && <p role="status">正在读取最近项目…</p>}
    {folderProjects.error && <p role="alert">{folderProjects.error.message} <button onClick={() => void folderProjects.refetch()}>重试</button></p>}

    {folderProjects.data?.projects.length === 0 && <div className="workspace-projects-empty workspace-projects-codex-empty">
      <span className="workspace-projects-empty-icon"><FolderIcon /></span>
      <h3>开始一个新游戏项目</h3>
      <p>创建项目后，先和 AI 讨论需求并生成制作步骤；确认步骤后再授权执行。</p>
      <div>
        <button className="workspace-primary-action" onClick={() => { setError(''); setCreateOpen(true); }}>＋ 新建项目</button>
        <button className="workspace-secondary-action" onClick={() => showFolderBrowser('existing')}><FolderIcon />打开已有项目</button>
      </div>
    </div>}

    {!!folderProjects.data?.projects.length && <section className="workspace-recent-projects">
      <h3>最近项目</h3>
      <div className="workspace-project-list">
        {folderProjects.data.projects.map((project: FolderProject) => <div className={`workspace-project-card workspace-recent-project-card ${projectId === project.project_id ? 'is-selected' : ''}`} key={project.project_id}>
          <button className="workspace-project-open" aria-pressed={projectId === project.project_id} disabled={project.root_available === false || deletingProjectId === project.project_id} onClick={() => onSelect(project.project_id)}>
            <span><strong>{project.name}</strong><small>{project.root_path}</small>{project.root_available === false && <small>原登记目录不可用 · 请重新打开移动后的文件夹</small>}{project.project_kind === 'existing_unadopted' && <small>副本已登记 · 等待已有工程采用流程</small>}</span>
            <b>{project.root_available === false ? '重新定位' : projectId === project.project_id ? '当前' : '打开'}</b>
          </button>
          <button className="workspace-project-delete" type="button" aria-label={`删除 ${project.name}`} disabled={deletingProjectId === project.project_id} onClick={() => void forgetFolderProject(project)}>{deletingProjectId === project.project_id ? '删除中…' : '删除'}</button>
        </div>)}
      </div>
    </section>}

    <details className="workspace-projects-legacy"><summary>原有项目与独立对话</summary><div className="workspace-project-list">
      <button className={`workspace-project-card ${!projectId ? 'is-selected' : ''}`} onClick={() => onSelect(null)} aria-pressed={!projectId}><span><strong>独立对话</strong><small>不附带项目上下文</small></span><b>{!projectId ? '当前' : '选择'}</b></button>
      {projects.data?.projects.filter((project: Project) => !folderProjects.data?.projects.some((folder: FolderProject) => folder.project_id === project.project_id)).map((project: Project) => <button className={`workspace-project-card ${projectId === project.project_id ? 'is-selected' : ''}`} key={project.project_id} aria-pressed={projectId === project.project_id} onClick={() => onSelect(project.project_id)}><span><strong>{project.name}</strong><small>原有本地项目</small></span><b>{projectId === project.project_id ? '当前' : '选择'}</b></button>)}
    </div></details>

    {createOpen && <div className="workspace-project-dialog-layer">
      <form className="workspace-project-dialog" role="dialog" aria-modal="true" aria-label="新建项目" onSubmit={async event => {
        event.preventDefault();
        if (!folders.data) return;
        setBusy(true);
        setError('');
        try {
          const project = await workspaceClient.createFolderProject({ parent_path: folders.data.path, name: folderName.trim() });
          await refreshProjects();
          setFolderName('');
          setCreateOpen(false);
          onSelect(project.project_id);
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e));
        } finally {
          setBusy(false);
        }
      }}>
        <header><div><h3>新建项目</h3><p>SceneOps 将创建一个新的游戏工程文件夹。</p></div><button type="button" className="workspace-icon-button" aria-label="关闭新建项目" onClick={closeCreate}><CloseIcon /></button></header>
        <label className="workspace-project-name">项目名称<input autoFocus required maxLength={160} value={folderName} placeholder="例如：归途" onChange={event => setFolderName(event.target.value)} /></label>
        <button type="button" className="workspace-location-row" onClick={() => showFolderBrowser('create')}>
          <span className="workspace-location-icon"><FolderIcon /></span>
          <span><small>保存位置</small><strong>{folders.data?.path ?? '正在读取默认位置…'}</strong></span>
          <b>更改</b>
        </button>
        <p className="workspace-project-path-preview">将创建：{folders.data?.path ?? '…'}/{folderName.trim() || '项目名称'}</p>
        {error && <p className="workspace-project-error" role="alert">{error}</p>}
        <footer><button type="button" onClick={closeCreate}>取消</button><button className="workspace-primary-action" disabled={busy || !folderName.trim() || !folders.data || folders.isFetching}>{busy ? '创建中…' : '创建项目'}</button></footer>
      </form>
    </div>}

    {folderBrowserMode && <div className="workspace-project-dialog-layer workspace-folder-browser-layer">
      <section className="workspace-project-dialog workspace-folder-browser" role="dialog" aria-modal="true" aria-label={folderBrowserMode === 'create' ? '选择保存位置' : '打开项目'}>
        <header><div><h3>{folderBrowserMode === 'create' ? '选择保存位置' : '打开项目'}</h3><p>{folderBrowserMode === 'create' ? '选择新项目所在的父文件夹。' : '选择一个已经由 SceneOps 创建或登记的文件夹。'}</p></div><button type="button" className="workspace-icon-button" aria-label="关闭文件夹选择" onClick={() => { setFolderBrowserMode(null); setInspection(null); setError(''); }}><CloseIcon /></button></header>
        <div className="workspace-path-entry">
          <label>文件夹路径<input value={pathInput} placeholder="输入绝对路径" onChange={event => setPathInput(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && pathInput.trim()) { event.preventDefault(); setBrowsePath(pathInput.trim()); setInspection(null); } }} /></label>
          <button type="button" disabled={!pathInput.trim()} onClick={() => { setBrowsePath(pathInput.trim()); setInspection(null); }}>前往</button>
        </div>
        {folders.isPending && <p role="status">正在读取目录…</p>}
        {folders.error && <p role="alert">{folders.error.message} <button type="button" onClick={() => void folders.refetch()}>重试</button></p>}
        {folders.data && <>
          <div className="workspace-current-folder"><FolderIcon /><span><small>当前文件夹</small><strong>{folders.data.path}</strong></span></div>
          <div className="workspace-folder-list" aria-label="子目录">
            {folders.data.parent_path && <button type="button" onClick={() => { setBrowsePath(folders.data?.parent_path ?? undefined); setPathInput(folders.data?.parent_path ?? ''); setInspection(null); }}><span className="workspace-folder-list-icon">↰</span><span><strong>上一级</strong></span></button>}
            {folders.data.entries.filter((entry: FolderEntry) => showHidden || !entry.name.startsWith('.')).map((entry: FolderEntry) => <button type="button" key={entry.path} disabled={!entry.selectable} onClick={() => { setBrowsePath(entry.path); setPathInput(entry.path); setInspection(null); }}><span className="workspace-folder-list-icon"><FolderIcon /></span><span><strong>{entry.name}</strong>{!entry.selectable && <small>符号链接不可选</small>}</span><b>›</b></button>)}
            {folders.data.entries.filter((entry: FolderEntry) => showHidden || !entry.name.startsWith('.')).length === 0 && <p>此文件夹中没有子目录。</p>}
          </div>
          <label className="workspace-show-hidden"><input type="checkbox" checked={showHidden} onChange={event => setShowHidden(event.target.checked)} />显示隐藏目录</label>
        </>}
        {inspection && <div className="workspace-identity-review" role="status">
          <strong>{inspectionTitle(inspection)}</strong>
          <p>{inspection.message}</p>
          {inspection.registered_root_path && inspection.registered_root_path !== inspection.path && <small>原登记位置：{inspection.registered_root_path}</small>}
          <div className="workspace-identity-actions">
            {(inspection.allowed_resolutions ?? []).includes('restore') && <button type="button" disabled={identityBusy} onClick={() => void recoverCurrentFolder('restore')}>恢复本机登记</button>}
            {(inspection.allowed_resolutions ?? []).includes('move') && <button type="button" disabled={identityBusy} onClick={() => void recoverCurrentFolder('move')}>确认是移动后的原项目</button>}
            {(inspection.allowed_resolutions ?? []).includes('copy') && <button type="button" disabled={identityBusy} onClick={() => void recoverCurrentFolder('copy')}>作为副本登记</button>}
          </div>
        </div>}
        {error && <p className="workspace-project-error" role="alert">{error}</p>}
        <footer><button type="button" onClick={() => { setFolderBrowserMode(null); setInspection(null); setError(''); }}>取消</button>{folderBrowserMode === 'create' ? <button type="button" className="workspace-primary-action" disabled={!folders.data} onClick={() => { setFolderBrowserMode(null); setInspection(null); }}>使用此位置</button> : <button type="button" className="workspace-primary-action" disabled={!folders.data || identityBusy} onClick={() => void inspectAndOpenCurrentFolder()}>{identityBusy ? '正在检查…' : '打开此文件夹'}</button>}</footer>
      </section>
    </div>}

    <details className="workspace-projects-legacy"><summary>高级：创建不绑定文件夹的旧版项目</summary><form onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError('');
      try { const project = await workspaceClient.create({ name: name.trim() }); await cache.invalidateQueries({ queryKey: ['workspace-projects'] }); setName(''); onSelect(project.project_id); }
      catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
    }} className="workspace-project-create"><div><span className="tool-kicker">NEW LOCAL PROJECT</span><h3>新建项目</h3><p>此入口保留旧版流程，不进入新策划旅程。</p></div><label>项目名称 <input required maxLength={160} value={name} placeholder="例如：归途" onChange={e => setName(e.target.value)} /></label><button disabled={busy || !name.trim()}>{busy ? '创建中…' : '创建空项目'}</button></form></details>
    {error && !createOpen && !folderBrowserMode && <p className="workspace-project-error" role="alert">{error}</p>}
  </section>;
}
