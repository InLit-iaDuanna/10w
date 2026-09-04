import React, { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  EditorRegistry, WorkspaceRegistry, WorkbenchCommandBus, WorkbenchEventBus,
  WorkspaceCoordinator, VisibilityCoordinator, EdgeDrawerCoordinator,
  LayoutRepository, createWorkspaceFromPreset, HOME_PRESET, EMPTY_WORKBENCH_CONTEXT,
  createShellCommandDefinitions, ShellToolRuntimeContext,
  type EditorHostProps, type EditorPlacement, type CommandExecutionContext, type Edge, type JsonValue,
} from '@sceneops/forge-shell';
import {
  assistantConversationEditor, ConversationController, ConversationRepository,
  CodeBuddyConversationTransport, createConversationEditorRuntime,
} from '@sceneops/conversation-home';
import { resolveFrontendModuleStates } from '@sceneops/module-runtime';
import { generatedFrontendModuleCatalog } from '../registries/generated-module-catalog';
import { ForgeShell } from '../shell/ForgeShell';
import { BindableDockingPort } from '../shell/BindableDockingPort';
import { createForgeShellRuntime } from '../shell/createForgeShellRuntime';
import { conversationCommandBridge } from './conversationBridge';
import './workbench.css';

const layoutKey = 'sceneops.lab.shell.layout.v3';
function createWorkbench() {
  const events = new WorkbenchEventBus();
  const commands = new WorkbenchCommandBus();
  const editors = new EditorRegistry();
  const workspaces = new WorkspaceRegistry();
  const engine = new BindableDockingPort();
  const context: CommandExecutionContext = {
    workbench: structuredClone(EMPTY_WORKBENCH_CONTEXT), source: 'button',
    permissions: new Set(['conversation:read', 'conversation:write', 'workbench:read', 'workbench:write']),
    connectedIntegrations: new Set(),
  };
  const transport = new CodeBuddyConversationTransport();
  const queryClient = new QueryClient();
  const controller = new ConversationController(new ConversationRepository(localStorage, sessionStorage), transport);
  const initialized = controller.initialize({ kind: 'pre_project', sessionId: 'lab_shell' });
  if (initialized.status === 'failed') throw new Error(initialized.error.message);
  const conversation = createConversationEditorRuntime({
    controller, commandBus: conversationCommandBridge(commands, context),
    getWorkbenchContext: () => context.workbench, getContextSummary: () => context.workbench,
    getConversationAvailability: () => ({ state: 'connected', mode: transport.availabilityMode, message: transport.selectedModel === 'mock' ? 'MOCK · 确定性对话。试试“打开工具库”或“打开命令搜索”。' : `planned · CodeBuddy ${transport.selectedModel}，发送时检查登录和额度。` }),
    attachmentStager: { async stage() { throw new Error('BLOCKED · 本工作台未接入附件导入服务，请使用项目工作台。'); } },
  });
  const states = resolveFrontendModuleStates(generatedFrontendModuleCatalog.map(c => c.manifest), { runtime_fixture: false });
  for (const contribution of generatedFrontendModuleCatalog) {
    if (states.get(contribution.manifest.id)?.availability !== 'enabled') continue;
    for (const definition of contribution.editors) {
      if (!('load' in definition)) continue;
      if (definition.id === assistantConversationEditor.id) {
        editors.register({ ...assistantConversationEditor, async load() {
          const { default: Conversation } = await assistantConversationEditor.load();
          return { default: (props: EditorHostProps) => <Conversation {...props} localState={assistantConversationEditor.restoreState(props.localState)} runtime={conversation} modelTransport={transport} /> };
        } });
      } else editors.register(definition);
    }
  }
  workspaces.register(HOME_PRESET);
  const repository = new LayoutRepository(localStorage, editors);
  const loaded = repository.load(layoutKey, () => createWorkspaceFromPreset(HOME_PRESET, editors));
  const initial = loaded.document;
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
          coordinator.setContextBinding(instanceId, instance.contextBinding.mode === 'pinned' ? { mode: 'follow-global' } : { mode: 'pinned', context: context.workbench });
        } else await open('shell.tool-library', { mode: 'split', direction: 'right', relativeToInstanceId: instanceId });
        changed();
      };
      void operation().catch(report);
    },
  });
  return { initial, coordinator, engine, edges, runtime, changed, report, queryClient, getError: () => error,
    subscribe: (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
    tools: { editors: editors.list(), open, execute, save },
    async edgeChanged(edge: Edge) {
      const drawer = coordinator.getDrawer(edge);
      if (drawer.mode !== 'hidden' && drawer.tabs.length === 0) await open(edge === 'top' ? 'shell.command-search' : 'shell.tool-library', { mode: 'drawer', edge });
      changed();
    },
  };
}

export function ShellWorkbench() {
  const [workbench] = useState(() => { try { return { value: createWorkbench() }; } catch (error) { return { error: String(error) }; } });
  const [, refresh] = useState(0);
  const [ready, setReady] = useState(false);
  useEffect(() => workbench.value?.subscribe(() => refresh(v => v + 1)), [workbench]);
  if (!workbench.value) return <main role="alert">BLOCKED · 工作台启动失败：{workbench.error}</main>;
  const app = workbench.value;
  const document = ready ? app.coordinator.snapshot() : app.initial;
  const chatOnly = Object.values(document.instances).length === 1 && Object.values(document.instances)[0].editorId === 'assistant.conversation';
  return <div className={`workbench-root ${chatOnly ? 'is-chat-only' : ''}`}>
    <QueryClientProvider client={app.queryClient}><ShellToolRuntimeContext.Provider value={app.tools}>
      <ForgeShell document={document} runtime={app.runtime} edgeDrawers={app.edges} judgeMode={false}
        onDockviewReady={port => { app.engine.bind(port); setReady(true); }}
        onDockviewLayoutChanged={() => app.changed()}
        onEdgeChanged={edge => void app.edgeChanged(edge).catch(app.report)}
        onFloatingToolLibrary={() => void app.tools.open('shell.tool-library', { mode: 'floating' }).catch(app.report)} />
    </ShellToolRuntimeContext.Provider></QueryClientProvider>
    {app.getError() && <aside className="workbench-error" role="alert">{app.getError()}</aside>}
  </div>;
}
