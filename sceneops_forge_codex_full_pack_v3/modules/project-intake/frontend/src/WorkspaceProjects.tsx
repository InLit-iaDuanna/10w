import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { workspaceClient } from '@sceneops/workspace-client';

export function WorkspaceProjects({ projectId, onSelect }: { projectId: string | null; onSelect(id: string | null): void }) {
  const cache = useQueryClient();
  const projects = useQuery({ queryKey: ['workspace-projects'], queryFn: workspaceClient.projects });
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  return <section className="shell-tool-content" aria-label="本地项目">
    <header className="workspace-projects-header"><span className="tool-kicker">PROJECT CONTEXT</span><h2>本地项目</h2><p>选择此轮生产计划的上下文。项目和已保存草稿只保存在本机；创建项目不会导入示例或启动作业。</p></header>
    {projects.isPending && <p role="status">正在读取本地项目…</p>}
    {projects.error && <p role="alert">{projects.error.message} <button onClick={() => void projects.refetch()}>重试</button></p>}
    {projects.data?.projects.length === 0 && <div className="workspace-projects-empty"><strong>空工作区</strong><span>先创建一个本地项目，再开始整理目标和生产计划。</span></div>}
    <div className="workspace-project-list"><button className={`workspace-project-card ${!projectId ? 'is-selected' : ''}`} onClick={() => onSelect(null)} aria-pressed={!projectId}><span><strong>未选择项目</strong><small>保留为独立对话，不附带项目上下文</small></span><b>{!projectId ? '当前' : '选择'}</b></button>
    {projects.data?.projects.map(project => <button className={`workspace-project-card ${projectId === project.project_id ? 'is-selected' : ''}`} key={project.project_id} aria-pressed={projectId === project.project_id} onClick={() => onSelect(project.project_id)}><span><strong>{project.name}</strong><small>本地上下文 · planned</small></span><b>{projectId === project.project_id ? '当前' : '选择'}</b></button>)}</div>
    <form onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError('');
      try { const project = await workspaceClient.create({ name: name.trim() }); await cache.invalidateQueries({ queryKey: ['workspace-projects'] }); setName(''); onSelect(project.project_id); }
      catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
    }} className="workspace-project-create"><div><span className="tool-kicker">NEW LOCAL PROJECT</span><h3>新建项目</h3><p>从空白项目开始，再通过对话定义目标与约束。</p></div><label>项目名称 <input required maxLength={160} value={name} placeholder="例如：归途" onChange={e => setName(e.target.value)} /></label><button disabled={busy || !name.trim()}>{busy ? '创建中…' : '创建空项目'}</button></form>
    {error && <p role="alert">{error}</p>}
  </section>;
}
