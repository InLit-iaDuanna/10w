import { useEffect, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChatComposer, MarkdownMessage } from '@sceneops/core-ui';
import { exportApi, exportKeys, type ExportPlatform, type ExportTask } from './client';
import { ExportNativeActivity } from './ExportNativeActivity';
import { ExportPlatformCard, platformNames } from './ExportPlatformCard';
import './export.css';

export interface ExportWorkbenchProps {
  projectId: string;
  projectName?: string;
  onOpenModelSettings?: () => void;
  modelPicker?: ReactNode;
  onRequestDevelopment?: (request: string) => void;
}

export function ExportWorkbench(props: ExportWorkbenchProps) {
  return <div className="export-container"><ProjectExportWorkbench key={props.projectId} {...props} /></div>;
}

function ProjectExportWorkbench({ projectId, projectName, onRequestDevelopment, onOpenModelSettings, modelPicker }: ExportWorkbenchProps) {
  const cache = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [appName, setAppName] = useState(projectName ?? '');
  const [appId, setAppId] = useState('');
  const [orientation, setOrientation] = useState<'landscape' | 'portrait'>('landscape');
  const [createMode, setCreateMode] = useState<'native' | 'fixed'>('native');
  const [allowDependencyInstall, setAllowDependencyInstall] = useState(false);
  const [platforms, setPlatforms] = useState<ExportPlatform[]>(['android']);
  const [executionMode, setExecutionMode] = useState<'native' | 'discuss'>('native');
  const [message, setMessage] = useState('');
  const [disconnected, setDisconnected] = useState(false);
  const list = useQuery({ queryKey: exportKeys.list(projectId), queryFn: () => exportApi.list(projectId) });
  const taskId = creating ? null : selectedId ?? list.data?.[0]?.id ?? null;
  const detail = useQuery({ queryKey: exportKeys.task(projectId, taskId ?? ''), queryFn: () => exportApi.get(projectId, taskId!), enabled: !!taskId });
  const task = detail.data;
  const nativeBusy = task?.native_runs?.some(run => ['queued', 'running', 'cancel_pending'].includes(run.status)) ?? false;
  function receive(updated: ExportTask) {
    cache.setQueryData(exportKeys.task(projectId, updated.id), (previous: ExportTask | undefined) => !previous || updated.revision >= previous.revision ? updated : previous);
    void cache.invalidateQueries({ queryKey: exportKeys.list(projectId) });
  }
  const mutation = useMutation({ mutationFn: (operation: () => Promise<ExportTask>) => operation(), onSuccess: receive });
  useEffect(() => {
    if (!taskId) return;
    setDisconnected(false);
    const events = new EventSource(exportApi.events(projectId, taskId));
    events.onopen = () => setDisconnected(false);
    events.onerror = () => setDisconnected(true);
    const onSnapshot = (event: MessageEvent) => {
      try {
        const updated = JSON.parse(event.data) as ExportTask;
        if (updated.project_id !== projectId || updated.id !== taskId) throw new Error('导出事件身份不匹配');
        receive(updated); setDisconnected(false);
      } catch { setDisconnected(true); }
    };
    events.addEventListener('snapshot', onSnapshot);
    return () => events.close();
  }, [projectId, taskId, cache]);
  useEffect(() => { setMessage(''); mutation.reset(); }, [taskId]);

  const create = () => mutation.mutate(async () => {
    const created = await exportApi.create(projectId, { platforms, execution_mode: createMode, accept_full_access: createMode === 'native', settings: { app_name: appName.trim(), app_id: appId.trim(), orientation, allow_dependency_install: allowDependencyInstall } });
    setSelectedId(created.id); setCreating(false); return created;
  });
  const send = () => {
    if (!taskId || !message.trim() || mutation.isPending || nativeBusy) return;
    const content = message.trim();
    mutation.mutate(() => exportApi.message(projectId, taskId, { content, execution_mode: executionMode, accept_full_access: executionMode === 'native' }), { onSuccess: () => setMessage('') });
  };
  const error = mutation.error ?? detail.error ?? list.error;
  return <div className="export-workbench">
    <section className="export-main" aria-label="导出设置与产物">
      <header className="export-heading"><div><h2>导出</h2><p className="export-muted">安卓与电脑试玩包</p></div><button onClick={() => { setCreating(true); mutation.reset(); }}>新建导出</button></header>
      {error && <div role="alert" className="export-error">{error.message}<button onClick={() => { void list.refetch(); if (taskId) void detail.refetch(); }}>重新读取</button></div>}
      {list.isPending && <p role="status">正在读取导出记录…</p>}
      {!list.isPending && !taskId && <form className="export-settings" onSubmit={event => { event.preventDefault(); create(); }}>
        <label>应用名称<input value={appName} placeholder="沿用项目名称" onChange={event => setAppName(event.target.value)} /></label>
        <label>应用标识<input value={appId} placeholder="根据项目 ID 自动生成" onChange={event => setAppId(event.target.value)} /></label>
        <fieldset><legend>目标平台</legend>{Object.entries(platformNames).map(([value, label]) => <label key={value} className="export-checkbox"><input type="checkbox" checked={platforms.includes(value as ExportPlatform)} onChange={event => setPlatforms(current => event.target.checked ? [...current, value as ExportPlatform] : current.filter(item => item !== value))} />{label}</label>)}</fieldset>
        {platforms.includes('android') && <label>安卓屏幕方向<select value={orientation} onChange={event => setOrientation(event.target.value as 'landscape' | 'portrait')}><option value="landscape">横屏</option><option value="portrait">竖屏</option></select></label>}
        <label>导出方式<select aria-label="导出方式" value={createMode} onChange={event => setCreateMode(event.target.value as 'native' | 'fixed')}><option value="native">Agent 导出</option><option value="fixed">固定流程构建</option></select></label>
        {createMode === 'fixed' && <label className="export-checkbox"><input type="checkbox" checked={allowDependencyInstall} onChange={event => setAllowDependencyInstall(event.target.checked)} />固定构建流程：允许在本次导出目录下载项目与打包依赖</label>}
        {createMode === 'native' && <p className="export-muted">开始即允许 Agent 在当前电脑执行命令、安装所需工具、修复导出配置并继续打包，可操作导出目录以外的环境；不修改游戏玩法、不公开发布。</p>}
        <button type="submit" disabled={mutation.isPending || !platforms.length}>{mutation.isPending ? '正在创建…' : createMode === 'native' ? '让 Agent 开始导出' : '开始固定构建'}</button>
        <p className="export-muted">在当前电脑构建，产物用于本地试玩。缺少工具时，可让右侧 Agent 补齐并继续。</p>
      </form>}
      {taskId && detail.isPending && <p role="status">正在恢复导出任务…</p>}
      {task && <><p>{task.settings.app_name} <span className="export-muted">· {task.mode}</span></p><p className="export-source">来源版本：{task.source_version}</p>
        <div className="export-actions"><button disabled={mutation.isPending || nativeBusy} onClick={() => mutation.mutate(async () => {
          const refreshed = await exportApi.refreshSource(projectId, task.id);
          setSelectedId(refreshed.id); setCreating(false); return refreshed;
        })}>用当前项目重新导出</button>{task.previous_task_id && <button onClick={() => setSelectedId(task.previous_task_id!)}>查看上一导出任务</button>}</div>
        <p className="export-muted">继续导出沿用原始来源。源码修改保存后，使用当前项目重新导出，生成新的任务并保留对话。</p>
        <label className="export-checkbox"><input type="checkbox" checked={task.settings.allow_dependency_install} disabled={mutation.isPending} onChange={event => {
          const allow_dependency_install = event.target.checked;
          mutation.mutate(() => exportApi.consent(projectId, task.id, { allow_dependency_install }));
        }} />固定构建流程：允许下载项目与打包依赖</label>
        <p className="export-muted">仅应用于后续执行轮次。保存后，可继续需要处理的平台。</p>
        {task.platforms.map(platform => <ExportPlatformCard key={`${task.id}:${platform.platform}`} platform={platform} busy={mutation.isPending || nativeBusy}
          onAction={(target, action) => mutation.mutate(() => exportApi.platformAction(projectId, task.id, target, action))}
          onVerify={(target, status, notes, device, attempt_id) => mutation.mutate(() => exportApi.verify(projectId, task.id, target, { status, notes, device, attempt_id }))} />)}</>}
      {!!list.data?.length && <section className="export-history"><h3>导出记录</h3>{list.data.map(item => <button key={item.id} aria-pressed={taskId === item.id} onClick={() => { setSelectedId(item.id); setCreating(false); }}><span>{item.settings.app_name}</span><time>{new Date(item.created_at).toLocaleString()}</time></button>)}</section>}
    </section>
    <section className="export-chat" aria-label="导出 Agent 对话">
      <header className="export-heading"><h3>导出 Agent</h3>{modelPicker}{onOpenModelSettings && <button onClick={onOpenModelSettings}>模型设置</button>}</header>
      {disconnected && <p role="alert" className="export-error">实时连接已断开，正在重连。任务仍在本机保留。<button onClick={() => void detail.refetch()}>刷新状态</button></p>}
      <div className="export-messages" aria-live="polite">
        {!task && <p className="export-muted">创建或选择导出任务后，在这里与 Agent 讨论打包问题。</p>}
        {task && !task.messages?.length && <p className="export-muted">遇到问题可以直接描述需求，Agent 会读取本次任务与构建日志。</p>}
        {task?.messages?.map(item => <article key={item.id} className={`export-message export-message-${item.role}`}><small>{item.role === 'user' ? '你' : item.role === 'assistant' ? 'Agent' : '任务记录'}</small><MarkdownMessage text={item.content} />{item.proposed_development && onRequestDevelopment && <button onClick={() => onRequestDevelopment(`导出任务 ${task.id}（来源 ${task.source_version}）：\n${item.proposed_development}`)}>交给开发对话确认修改</button>}</article>)}
        {task && <ExportNativeActivity runs={task.native_runs ?? []} />}
        {mutation.isPending && <p role="status">正在处理…</p>}
      </div>
      <ChatComposer onSubmit={event => { event.preventDefault(); send(); }}
        input={<textarea aria-label="给导出 Agent 的消息" placeholder="描述导出问题，或让 Agent 继续处理…" value={message} disabled={!taskId} onChange={event => setMessage(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send(); } }} />}
        options={<label className="export-mode">处理方式<select aria-label="导出 Agent 处理方式" value={executionMode} disabled={nativeBusy || mutation.isPending} onChange={event => setExecutionMode(event.target.value as 'native' | 'discuss')}><option value="native">操作电脑并继续导出</option><option value="discuss">仅讨论</option></select></label>}
        actions={<>{nativeBusy && <button type="button" disabled={mutation.isPending || task?.native_runs?.some(run => run.cancel_requested && ['queued', 'running', 'cancel_pending'].includes(run.status))} onClick={() => mutation.mutate(() => exportApi.cancelAgent(projectId, taskId!))}>停止 Agent</button>}<button type="submit" disabled={!taskId || !message.trim() || mutation.isPending || nativeBusy}>{executionMode === 'native' ? '发送并执行' : '发送讨论'}</button></>}
        notice={<div><p className="export-muted">{executionMode === 'native' ? '发送即允许 Agent 在当前电脑执行命令、安装所需工具、修复导出配置并继续打包，可操作导出目录以外的环境；不修改游戏玩法、不公开发布。' : '仅讨论问题，不操作电脑。'}</p>{onRequestDevelopment && task && <button type="button" disabled={!message.trim() || mutation.isPending || nativeBusy} onClick={() => onRequestDevelopment(`导出任务 ${task.id}（来源 ${task.source_version}）需要游戏开发修改：\n${message.trim()}`)}>将输入内容交给开发对话确认</button>}</div>} />
    </section>
  </div>;
}

export default ExportWorkbench;
