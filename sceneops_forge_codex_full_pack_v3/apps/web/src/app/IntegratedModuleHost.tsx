import React, { lazy, Suspense, useCallback, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { agentTasks, ProjectProductionTool, ProductionModuleView, type ProductionSelection } from '@sceneops/ai-agent-runtime';
import type { EditorHostProps, IntegratedWorkbenchProps, WorkbenchContext } from '@sceneops/core-ui';
import { workspaceClient, type ModuleId } from '@sceneops/workspace-client';

export interface IntegratedActions {
  projectAssets(projectId:string,suspended:boolean):React.ReactNode;
  selectProject(id: string | null): void;
  openProjects(): void;
  updateContext(instanceId: string, patch: Partial<WorkbenchContext>): void;
  setDirty(instanceId: string, source: string, dirty: boolean): void;
  discuss(selection: ProductionSelection): void;
  produceDocument(projectId:string,moduleId:ModuleId,revision:number,payload:unknown):void;
}

export function createIntegratedModuleHost(moduleId: ModuleId, title: string,
  load: () => Promise<{default: React.ComponentType<IntegratedWorkbenchProps>}>, actions: IntegratedActions) {
  const Workbench = lazy(load);
  function ProjectModule(props: EditorHostProps) {
    const id = props.context.projectId!;
    const cache = useQueryClient();
    const key = ['workspace-document', id, moduleId];
    const projects = useQuery({ queryKey: ['workspace-projects'], queryFn: workspaceClient.projects });
    const document = useQuery({ queryKey: key, queryFn: () => workspaceClient.document(id, moduleId), retry: false });
    const [error, setError] = useState('');
    const [importing, setImporting] = useState(false);
    const [advancedOpened, setAdvancedOpened] = useState(false);
    const dirty = useCallback((value: boolean) => actions.setDirty(props.instanceId, 'draft', value), [props.instanceId]);
    const contextChanged = useCallback((patch: Partial<WorkbenchContext>) => actions.updateContext(props.instanceId, patch), [props.instanceId]);
    const project = projects.data?.projects.find(project => project.project_id === id);
    if (projects.error || document.error) return <section className="shell-tool-content" role="alert">{(projects.error ?? document.error)?.message} <button onClick={() => { void projects.refetch(); void document.refetch(); }}>重试</button></section>;
    if (!document.data || projects.isPending) return <p className="shell-tool-content">正在读取本地草稿…</p>;
    if (!project) return <p className="shell-tool-content">项目不存在，请重新选择项目。</p>;
    const saved = document.data;
    async function importSample(sample: 'remember-home' | 'warehouse-escape') {
      if (!window.confirm('将导入明确标记为 Mock 的静态示例并替换当前模块草稿。不会执行案例。继续？')) return;
      setImporting(true); setError('');
      try { cache.setQueryData(key, await workspaceClient.sample(id, moduleId, {sample_id: sample, expected_revision: saved.revision})); }
      catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setImporting(false); }
    }
    if (moduleId === 'version-review') return <section className="integrated-module" aria-label="版本管理">
      <Suspense fallback={<p>正在加载版本树…</p>}><Workbench key={`${id}:${saved.sample_id ?? 'empty'}`} context={props.context} project={project} document={saved as IntegratedWorkbenchProps['document']}
        suspended={props.suspended} onContextChange={contextChanged} onDirtyChange={dirty}
        onSave={async payload => { cache.setQueryData(key, await workspaceClient.save(id, moduleId, { expected_revision: saved.revision, payload })); }} /></Suspense>
      {error && <p role="alert">{error}</p>}
      {!saved.sample_id && <details><summary>评审示例</summary><button disabled={importing} onClick={() => void importSample('remember-home')}>回家之路 · Mock</button><button disabled={importing} onClick={() => void importSample('warehouse-escape')}>仓库逃生 · Mock</button></details>}
    </section>;
    return <section className="integrated-module" aria-label={title}>
      <header className="integrated-module-header"><strong>{title}</strong> <small>{project.name} · 生产记录</small>
      </header>
      {error && <p role="alert">{error}</p>}
      {!saved.sample_id&&<button disabled={!Object.keys(saved.payload??{}).length} onClick={()=>actions.produceDocument(id,moduleId,saved.revision,saved.payload)}>按已保存配置修改当前游戏 →</button>}
      <p>保存配置后可交给当前项目的 AI 制作会话。已生成模型使用资产引用；界面、声音、动画和逻辑配置需要实际制作、构建与试玩后才算应用。</p>
      {moduleId==='character-animation'&&actions.projectAssets(id,props.suspended)}
      <ProjectProductionTool projectId={id} compact/>
      <details className="integrated-module-advanced" onToggle={event => { if (event.currentTarget.open) setAdvancedOpened(true); }}>
        <summary>高级 · 手动配置与原工作台</summary>
        {!saved.sample_id && <details><summary>手动导入 Mock 示例</summary><button disabled={importing} onClick={() => void importSample('remember-home')}>回家之路 · Mock</button> <button disabled={importing} onClick={() => void importSample('warehouse-escape')}>仓库逃生 · Mock</button></details>}
        {advancedOpened && <Suspense fallback={<p>正在加载工作台…</p>}><Workbench key={`${id}:${saved.sample_id ?? 'empty'}`} context={props.context} project={project} document={saved as IntegratedWorkbenchProps['document']}
          suspended={props.suspended} onContextChange={contextChanged} onDirtyChange={dirty}
          onRegisterInput={file=>agentTasks.uploadProjectInput(id,file)}
          onSave={async payload => { cache.setQueryData(key, await workspaceClient.save(id, moduleId, { expected_revision: saved.revision, payload })); }} /></Suspense>}
      </details>
    </section>;
  }
  return function IntegratedModule(props: EditorHostProps) {
    if (!props.context.projectId && moduleId === 'version-review') return <section className="shell-tool-content"><p>选择本地项目后查看 Git 版本树。</p><button onClick={actions.openProjects}>选择项目</button></section>;
    if (!props.context.projectId) return <section className="shell-tool-content" aria-label={title}><h2>{title}</h2><ProductionModuleView projectId={null} moduleId={moduleId} onDiscuss={actions.discuss} /><details><summary>高级 · 选择现有项目</summary><button onClick={actions.openProjects}>选择或创建项目</button></details></section>;
    return <ProjectModule key={props.context.projectId} {...props} />;
  };
}
