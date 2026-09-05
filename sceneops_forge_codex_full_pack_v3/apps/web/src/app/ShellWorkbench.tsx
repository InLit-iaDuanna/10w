import React, { useCallback, useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  EditorRegistry, WorkspaceRegistry, WorkbenchCommandBus, WorkbenchEventBus,
  WorkspaceCoordinator, VisibilityCoordinator, EdgeDrawerCoordinator,
  LayoutRepository, createWorkspaceFromPreset, HOME_PRESET, EMPTY_WORKBENCH_CONTEXT,
  createShellCommandDefinitions, ShellToolRuntimeContext,
  type EditorHostProps, type EditorPlacement, type CommandExecutionContext, type DrawerState, type Edge, type JsonValue, type WorkbenchContext,
} from '@sceneops/forge-shell';
import {
  assistantConversationEditor, ConversationController, ConversationRepository,
  CodeBuddyConversationTransport, createConversationEditorRuntime,
  UnifiedConversation,
} from '@sceneops/conversation-home';
import { WorkspaceProjects } from '@sceneops/project-intake';
import { integratedWorkbenches } from '../registries/generated-workbench-catalog';
import { createIntegratedModuleHost, type IntegratedActions } from './IntegratedModuleHost';
import { resolveFrontendModuleStates } from '@sceneops/module-runtime';
import { generatedFrontendModuleCatalog } from '../registries/generated-module-catalog';
import { ForgeShell } from '../shell/ForgeShell';
import { BindableDockingPort } from '../shell/BindableDockingPort';
import { createForgeShellRuntime } from '../shell/createForgeShellRuntime';
import { conversationCommandBridge } from './conversationBridge';
import './workbench.css';

function createWorkbench(unified: boolean) {
  const layoutKey = unified ? 'sceneops.unified.layout.v1' : 'sceneops.lab.shell.layout.v3';
  const events = new WorkbenchEventBus();
  const commands = new WorkbenchCommandBus();
  const editors = new EditorRegistry();
  const workspaces = new WorkspaceRegistry();
  const engine = new BindableDockingPort();
  const context: CommandExecutionContext = {
    workbench: {...structuredClone(EMPTY_WORKBENCH_CONTEXT), projectId: unified ? localStorage.getItem('sceneops.unified.selected-project') : null}, source: 'button',
    permissions: new Set(['conversation:read', 'conversation:write', 'workbench:read', 'workbench:write']),
    connectedIntegrations: new Set(),
  };
  const transport = unified ? null : new CodeBuddyConversationTransport();
  const queryClient = new QueryClient({defaultOptions:{queries:{retry:false, refetchOnWindowFocus:false}, mutations:{retry:false}}});
  const controller = transport ? new ConversationController(new ConversationRepository(localStorage, sessionStorage), transport) : null;
  const initialized = controller?.initialize({ kind: 'pre_project', sessionId: 'lab_shell' });
  if (initialized?.status === 'failed') throw new Error(initialized.error.message);
  const conversation = controller && transport ? createConversationEditorRuntime({
    controller, commandBus: conversationCommandBridge(commands, context),
    getWorkbenchContext: () => context.workbench, getContextSummary: () => context.workbench,
    getConversationAvailability: () => ({ state: 'connected', mode: transport.availabilityMode, message: transport.selectedModel === 'mock' ? 'MOCK · 确定性对话。试试“打开工具库”或“打开命令搜索”。' : `planned · CodeBuddy ${transport.selectedModel}，发送时检查登录和额度。` }),
    attachmentStager: { async stage() { throw new Error('BLOCKED · 本工作台未接入附件导入服务，请使用项目工作台。'); } },
  }) : null;
  const dirties = new Map<string, Set<string>>();
  const actions: IntegratedActions = {
    setDirty(instanceId, source, dirty) {
      const instance = coordinator.getInstance(instanceId);
      if (!instance) return;
      const sources = dirties.get(instanceId) ?? new Set<string>();
      if (dirty) sources.add(source); else sources.delete(source);
      dirties.set(instanceId, sources);
      if (instance.dirty !== !!sources.size) coordinator.setDirty(instanceId, !!sources.size);
    },
    selectProject(id) {
      if (context.workbench.projectId === id) return;
      const following = Object.values(coordinator.snapshot().instances).filter(i => i.contextBinding.mode === 'follow-global');
      if (following.some(i => i.dirty) && !window.confirm('有未保存修改。切换项目将丢弃这些修改，是否继续？')) return;
      context.workbench = {...structuredClone(EMPTY_WORKBENCH_CONTEXT), projectId: id};
      if (id) localStorage.setItem('sceneops.unified.selected-project', id); else localStorage.removeItem('sceneops.unified.selected-project');
      for (const instance of following) { dirties.delete(instance.instanceId); if (instance.dirty) coordinator.setDirty(instance.instanceId, false); }
      events.emit('workbench.layout.changed@1', {workspaceId: initial.workspaceId, operation: 'project-context'});
    },
    openProjects() { void open('workspace.projects', {mode:'drawer',edge:'left'}).catch(report); },
    updateContext(instanceId, patch) {
      const instance = coordinator.getInstance(instanceId);
      if (instance?.contextBinding.mode === 'pinned') coordinator.setContextBinding(instanceId, {mode:'pinned',context:{...instance.contextBinding.context,...patch}});
      else { context.workbench = {...context.workbench,...patch}; events.emit('workbench.layout.changed@1', {workspaceId: initial.workspaceId, operation:'selection-context'}); }
    },
  };
  const states = resolveFrontendModuleStates(generatedFrontendModuleCatalog.map(c => c.manifest), { runtime_fixture: false });
  for (const contribution of generatedFrontendModuleCatalog) {
    if (states.get(contribution.manifest.id)?.availability !== 'enabled') continue;
    for (const definition of contribution.editors) {
      if (!('load' in definition)) continue;
      if (definition.id === assistantConversationEditor.id) {
        editors.register({ ...assistantConversationEditor, async load() {
          if (unified) return {default: function ConversationHost(props: EditorHostProps) {
            const dirty = useCallback((value: boolean) => actions.setDirty(props.instanceId, 'chat', value), [props.instanceId]);
            return <UnifiedConversation context={props.context} onDirtyChange={dirty} onOpenPipeline={() => void open('harness.pipeline', {mode:'split',direction:'right'}).catch(report)} />;
          }};
          const { default: Conversation } = await assistantConversationEditor.load();
          return { default: (props: EditorHostProps) => <Conversation {...props} localState={assistantConversationEditor.restoreState(props.localState)} runtime={conversation} modelTransport={transport} /> };
        } });
      } else editors.register(definition);
    }
  }
  if (unified) {
    const defaults = {icon:'panel',category:'工作台',defaultPlacement:{mode:'split',direction:'right'} as const,
      singleton:true, renderPolicy:'suspend-when-hidden' as const, initialState:()=>({}), serializeState:()=>({}), restoreState:()=>({})};
    editors.register({...defaults,id:'workspace.projects',title:'本地项目',async load(){return {default:(props:EditorHostProps)=><WorkspaceProjects projectId={props.context.projectId} onSelect={actions.selectProject}/>};}});
    editors.register({...defaults,id:'harness.pipeline',title:'AI 生产计划',category:'AI 制作',async load(){
      const {PipelineWorkbench} = await import('@sceneops/ai-pipeline-compiler');
      return {default:function PipelineHost(props:EditorHostProps){
        const dirty = useCallback((value:boolean)=>actions.setDirty(props.instanceId,'pipeline',value),[props.instanceId]);
        return <PipelineWorkbench {...props} onDirtyChange={dirty} onOpenProjects={actions.openProjects}/>;
      }};
    }});
    for (const group of integratedWorkbenches) {
      const Component = createIntegratedModuleHost(group.id, group.title, group.load, actions);
      editors.register({...defaults,id:`workbench.${group.id}`,title:group.title,async load(){await group.load(); return {default:Component};}});
    }
  }
  workspaces.register(HOME_PRESET);
  const repository = new LayoutRepository(localStorage, editors);
  const loaded = repository.load(layoutKey, () => createWorkspaceFromPreset(HOME_PRESET, editors));
  const initial = loaded.document;
  if (unified) for (const instance of Object.values(initial.instances)) instance.dirty = false;
  const coordinator = new WorkspaceCoordinator({ document: initial, editors, workspaces, events, engine, environment: context });
  for (const command of createShellCommandDefinitions(coordinator)) commands.register(command);
  const edges = new EdgeDrawerCoordinator(structuredClone(initial.drawers), events);
  const listeners = new Set<() => void>();
  let saveTimer: ReturnType<typeof setTimeout>;
  const notify = () => { for (const listener of listeners) listener(); };
  const save = () => repository.save(layoutKey, coordinator.snapshot());
  const changed = () => { notify(); clearTimeout(saveTimer); saveTimer = setTimeout(() => { try { save(); } catch (e) { report(e); } }, 180); };
  let error = loaded.status === 'recovered' ? `已恢复默认布局：${loaded.reason}` : '';
  const report = (value: unknown) => { error = value instanceof Error ? value.message : String(value); notify(); };
  events.on('workbench.layout.changed@1', changed);
  events.on('workbench.context.binding_changed@1', changed);
  async function execute(id: string, input: JsonValue) {
    let result = await commands.execute<any>(id, context, input);
    if (result?.status === 'confirmation-required' && window.confirm('编辑器有未保存更改，确认继续？')) {
      result = await commands.execute<any>(id, context, { ...input as object, confirmed: true });
    }
    if (['rejected', 'unavailable'].includes(result?.status)) throw new Error(result.reason ?? result.code ?? result.status);
    for (const edge of ['left', 'right', 'top', 'bottom'] as Edge[]) edges.sync(coordinator.getDrawer(edge));
    changed();
  }
  const open = (editorId: string, placement: EditorPlacement) => execute('workbench.open_editor', { editorId, placement } as JsonValue);
  const runtime = createForgeShellRuntime({
    coordinator, editors, events, commands, visibility: new VisibilityCoordinator(events), getGlobalContext: () => context.workbench,
    onAreaAction(instanceId, action) {
      const operation = async () => {
        if (action === 'float') await execute('workbench.move_editor', { instanceId, placement: { mode: 'floating' } });
        else if (action === 'maximize-restore') await coordinator.toggleMaximize(instanceId);
        else if (action === 'follow-pin') {
          const instance = coordinator.getInstance(instanceId)!;
          if (instance.dirty && !window.confirm('更改上下文绑定可能丢弃未保存修改，继续？')) return;
          coordinator.setContextBinding(instanceId, instance.contextBinding.mode === 'pinned' ? { mode: 'follow-global' } : { mode: 'pinned', context: context.workbench });
        } else if (action === 'add') await open('shell.tool-library', { mode: 'tab', relativeToInstanceId: instanceId });
        else if (action === 'split') await open('shell.tool-library', { mode: 'split', direction: 'right', relativeToInstanceId: instanceId });
        else await execute('workbench.switch_editor', { instanceId, editorId: 'shell.tool-library' });
        changed();
      };
      void operation().catch(report);
    },
  });
  return { initial, coordinator, engine, edges, runtime, changed, report, queryClient, actions, getError: () => error,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    tools: { editors: editors.list(), open, execute, save },
    async edgeChanged(edge: Edge, requested: DrawerState) {
      const drawer = coordinator.getDrawer(edge);
      if (requested.mode !== 'hidden' && drawer.tabs.length === 0) await open('shell.tool-library', { mode: 'drawer', edge });
      // Creating an empty native edge can emit a collapsed layout before its
      // editor is attached. Finish the user's requested state, retaining new tabs.
      coordinator.syncDrawer({ ...coordinator.getDrawer(edge), mode: requested.mode,
        size: requested.size, lastOpenSize: requested.lastOpenSize });
      edges.sync(coordinator.getDrawer(edge));
      changed();
    },
  };
}

export function ShellWorkbench({ unified = false }: {unified?: boolean}) {
  const [workbench] = useState(() => { try { return { value: createWorkbench(unified) }; } catch (error) { return { error: String(error) }; } });
  const [, refresh] = useState(0);
  const [ready, setReady] = useState(false);
  useEffect(() => workbench.value?.subscribe(() => refresh(v => v + 1)), [workbench]);
  useEffect(() => {
    const prevent = (event: BeforeUnloadEvent) => { if (Object.values(workbench.value?.coordinator.snapshot().instances ?? {}).some(i => i.dirty)) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', prevent); return () => window.removeEventListener('beforeunload', prevent);
  }, [workbench]);
  if (!workbench.value) return <main role="alert">BLOCKED · 工作台启动失败：{workbench.error}</main>;
  const app = workbench.value;
  const document = ready ? app.coordinator.snapshot() : app.initial;
  const chatOnly = Object.values(document.instances).length === 1 && Object.values(document.instances)[0].editorId === 'assistant.conversation';
  return <div className={`workbench-root ${chatOnly ? 'is-chat-only' : ''}`}>
    {unified && <header className="workbench-appbar">
      <div className="workbench-brand"><span className="workbench-brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/></svg></span><strong>SceneOps</strong><small>制作工作台</small></div>
      <span className="workbench-appbar-hint">拖动四边，按需展开工具</span>
      <div className="workbench-appbar-actions"><button className="workbench-project-trigger" onClick={app.actions.openProjects}><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>本地项目</button><span className="workbench-local" title="项目和已保存内容存储在本机，不代表外部服务已连接。"><i aria-hidden="true"/>本地工作区</span></div>
    </header>}
    <div className="workbench-stage"><QueryClientProvider client={app.queryClient}><ShellToolRuntimeContext.Provider value={app.tools}>
      <ForgeShell document={document} runtime={app.runtime} edgeDrawers={app.edges} judgeMode={false}
        onDockviewReady={port => { app.engine.bind(port); setReady(true); }}
        onDockviewLayoutChanged={() => app.changed()}
        onEdgeChanged={(edge, requested) => void app.edgeChanged(edge, requested).catch(app.report)}
        onFloatingToolLibrary={() => void app.tools.open('shell.tool-library', { mode: 'floating' }).catch(app.report)} />
    </ShellToolRuntimeContext.Provider></QueryClientProvider></div>
    {app.getError() && <aside className="workbench-error" role="alert">{app.getError()}</aside>}
  </div>;
}
