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
    <h2>本地项目</h2><p>项目与已保存草稿保存在本机。新项目为空，不导入示例、不启动作业。</p>
    {projects.isPending && <p>正在读取本地项目…</p>}
    {projects.error && <p role="alert">{projects.error.message} <button onClick={() => void projects.refetch()}>重试</button></p>}
    {projects.data?.projects.length === 0 && <p>空工作区 · 尚未创建项目</p>}
    <p><button onClick={() => onSelect(null)} aria-pressed={!projectId}>未选择项目</button></p>
    {projects.data?.projects.map(project => <p key={project.project_id}><button aria-pressed={projectId === project.project_id} onClick={() => onSelect(project.project_id)}>{project.name}</button> <small>本地 · planned</small></p>)}
    <form onSubmit={async event => {
      event.preventDefault(); setBusy(true); setError('');
      try { const project = await workspaceClient.create({ name: name.trim() }); await cache.invalidateQueries({ queryKey: ['workspace-projects'] }); setName(''); onSelect(project.project_id); }
      catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
    }}><label>项目名称 <input required maxLength={160} value={name} onChange={e => setName(e.target.value)} /></label> <button disabled={busy || !name.trim()}>创建空项目</button></form>
    {error && <p role="alert">{error}</p>}
  </section>;
}
