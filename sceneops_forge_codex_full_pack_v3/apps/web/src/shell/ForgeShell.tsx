import 'dockview-enterprise';
import React, {
  Component,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  DockviewDefaultTab,
  DockviewReact,
  type DockviewApi,
  type DockviewReadyEvent,
  type IDockviewPanelHeaderProps,
  type IDockviewPanelProps,
} from 'dockview-react';
import 'dockview-react/dist/styles/dockview.css';
import {
  type AreaHeaderContract,
  type CloseEditorResult,
  type DockingMutationKind,
  type DockingTopology,
  type DrawerState,
  type Edge,
  type EdgeDrawerCoordinator,
  type EditorAvailability,
  type EditorHostProps,
  type EditorInstance,
  type EditorRegistry,
  type JsonValue,
  type LazyEditorModule,
  type VisibilityCoordinator,
  type WorkbenchCommandClient,
  type WorkbenchContext,
  type WorkbenchEventClient,
  type WorkspaceDocument,
} from '@sceneops/forge-shell';
import { AreaHeader } from './AreaHeader';
import { DockviewPort } from './DockviewPort';
import { EdgeDrawerController } from './EdgeDrawerController';
import { usePanelVisibility } from './hooks/usePanelVisibility';
import './forge-shell.css';
import { recordUiError, recordUiEvent } from '../debug';
import { RegionPullHandles, type RegionCollapseRequest, type RegionSplitRequest } from './RegionPullHandles';

export interface ForgeShellRuntime {
  editors: EditorRegistry;
  visibility: VisibilityCoordinator;
  commands: WorkbenchCommandClient;
  events: WorkbenchEventClient;
  getInstance(instanceId: string): EditorInstance | undefined;
  getDrawer(edge: Edge): DrawerState;
  syncDrawer(drawer: DrawerState): void;
  editorAvailability(editorId: string): EditorAvailability;
  updateVisibility(instanceId: string, visible: boolean): void;
  resolveContext(instanceId: string): WorkbenchContext;
  loadEditor(instanceId: string): Promise<LazyEditorModule | null>;
  updateLocalState(instanceId: string, patch: Partial<JsonValue>): void;
  close(instanceId: string, confirmed?: boolean): Promise<CloseEditorResult>;
  setTitle(instanceId: string, title: string): void;
  beginDockviewMutation(kind: DockingMutationKind): void;
  completeDockviewMutation(kind: DockingMutationKind, topology: DockingTopology): Promise<unknown>;
  syncDockviewLayout(layout: JsonValue, topology: DockingTopology): void;
  onAreaAction(instanceId: string, action: AreaHeaderContract['actions'][number]): void;
}

export interface ForgeShellProps {
  document: WorkspaceDocument;
  runtime: ForgeShellRuntime;
  edgeDrawers: EdgeDrawerCoordinator;
  judgeMode: boolean;
  onDockviewReady(port: DockviewPort, api: DockviewApi): void;
  onDockviewLayoutChanged(layout: JsonValue): void;
  onEdgeChanged(edge: Edge, requested: DrawerState): void;
  onFloatingToolLibrary(edge: Edge): void;
  onRegionSplit?(instanceId: string, edge: Edge): Promise<string | undefined>;
}

const RuntimeContext = createContext<ForgeShellRuntime | null>(null);
const MINIMAL_CHROME_EDITORS = new Set(['assistant.conversation', 'journey.modeling', 'journey.environment']);
const WORKFLOW_SIDEBAR_EDITORS = new Set(['journey.modeling', 'journey.environment']);
const groupClassReferences = new WeakMap<HTMLElement, Map<string, number>>();
const RegionPullContext = createContext<{
  split: RegionSplitRequest;
  collapse: RegionCollapseRequest;
} | null>(null);

export function ForgeShell(props: ForgeShellProps): React.ReactElement {
  const components = useMemo(() => ({ 'forge-editor-host': ForgeEditorPanel }), []);
  const [port, setPort] = useState<DockviewPort | null>(null);
  const sashDrag = useRef<{ layout: JsonValue; collapsed: Set<string> } | null>(null);
  const [regionError, setRegionError] = useState('');
  const hasWorkflowSidebar = Object.values(props.document.instances)
    .some(instance => WORKFLOW_SIDEBAR_EDITORS.has(instance.editorId));
  const splitBusy = useRef(false);
  const splitRegion = useCallback<RegionSplitRequest>(async (instanceId, edge, size) => {
    if (!port || !props.onRegionSplit || splitBusy.current) return;
    splitBusy.current = true;
    try {
      setRegionError('');
      const openedId = await props.onRegionSplit(instanceId, edge);
      if (openedId) {
        port.enableRegionSplits();
        if (size !== undefined) port.resizeRegion(openedId, edge, size);
        recordUiEvent('edge-state.changed', { instanceId: openedId, edge, mode: 'split', phase: 'complete' });
      }
    } catch (error) {
      recordUiError(error, { instanceId, edge, reason: 'layout-operation', phase: 'error' });
      setRegionError(error instanceof Error ? error.message : '区域拆分失败');
    } finally { splitBusy.current = false; }
  }, [port, props.onRegionSplit]);
  const collapseAdjacentRegion = useCallback<RegionCollapseRequest>(async (instanceId, edge, crossRatio) => {
    try {
      if (!port) return;
      const closingIds = port.adjacentRegionIds(instanceId, edge, crossRatio);
      if (closingIds.length === 0) return;
      const instances = closingIds.map(id => props.runtime.getInstance(id)).filter(instance => instance !== undefined);
      if (instances.some(instance => instance.locked)) {
        setRegionError('锁定的区域不能通过拖动收起。');
        return;
      }
      if (instances.some(instance => instance.dirty) &&
          !window.confirm('收起这个区域会关闭其中未保存的内容，仍要继续吗？')) return;
      setRegionError('');
      for (const id of closingIds) {
        if (!props.runtime.getInstance(id)) continue;
        const result = await props.runtime.close(id, true);
        if (result.status !== 'closed') throw new Error('相邻区域未能关闭');
      }
      recordUiEvent('edge-state.changed', { instanceId, edge, phase: 'complete' });
    } catch (error) {
      recordUiError(error, { instanceId, edge, reason: 'layout-operation', phase: 'error' });
      setRegionError(error instanceof Error ? error.message : '相邻区域收起失败');
    }
  }, [port, props.runtime]);
  const regionPull = useMemo(() => props.onRegionSplit
    ? { split: splitRegion, collapse: collapseAdjacentRegion }
    : null, [collapseAdjacentRegion, props.onRegionSplit, splitRegion]);
  const [restoreNotice, setRestoreNotice] = useState<{
    state: 'empty' | 'failed';
    message: string;
  } | null>(null);
  const handleEdgeChanged = useCallback((edge: Edge) => {
    const drawer = props.edgeDrawers.get(edge);
    props.runtime.syncDrawer(drawer);
    props.onEdgeChanged(edge, drawer);
  }, [port, props.edgeDrawers, props.onEdgeChanged, props.runtime]);
  const onReady = useCallback((event: DockviewReadyEvent) => {
    const readyPort = new DockviewPort(event.api);
    setPort(readyPort);
    props.onDockviewReady(readyPort, event.api);
    event.api.onWillMutateLayout((mutation) => {
      if (mutation.origin === 'user') {
        recordUiEvent('layout-mutation.begin', { phase: 'start', panelCount: event.api.panels.length });
        props.runtime.beginDockviewMutation(mutation.kind);
      }
    });
    event.api.onDidMutateLayout((mutation) => {
      if (mutation.origin === 'user') {
        void props.runtime.completeDockviewMutation(mutation.kind, readyPort.describe()).then(() => {
          recordUiEvent('layout-mutation.end', { phase: 'complete', panelCount: event.api.panels.length });
        }).catch(error => recordUiError(error, { phase: 'error', reason: 'layout-operation' }));
      }
    });
    const syncNativeLayout = () => {
      const layout = readyPort.capture();
      const topology = readyPort.describe();
      props.runtime.syncDockviewLayout(layout, topology);
      for (const edge of EDGES) props.edgeDrawers.sync(props.runtime.getDrawer(edge));
      props.onDockviewLayoutChanged(layout);
    };
    event.api.onDidLayoutChange(syncNativeLayout);
    const groupSubscriptions = new Map<string, Array<{ dispose(): void }>>();
    event.api.onDidAddGroup(group => {
      const onEdgeState = () => {
        syncNativeLayout();
        const location = group.api.location;
        if (location.type === 'edge') {
          const drawer = props.runtime.getDrawer(location.position);
          recordUiEvent('edge-state.changed', { edge: drawer.edge, mode: drawer.mode, size: drawer.size, phase: 'complete' });
        }
      };
      groupSubscriptions.set(group.id, [group.api.onDidCollapsedChange(onEdgeState), group.api.onDidPeekChange(onEdgeState)]);
    });
    event.api.onDidRemoveGroup(group => {
      groupSubscriptions.get(group.id)?.forEach(subscription => subscription.dispose());
      groupSubscriptions.delete(group.id);
    });
    void readyPort.restoreWorkspace(props.document).then(
      async (status) => {
        if (props.onRegionSplit) {
          const migrating = readyPort.describe().groups.some(group => group.location === 'edge');
          if (migrating) props.runtime.beginDockviewMutation('move');
          readyPort.enableRegionSplits();
          if (migrating) await props.runtime.completeDockviewMutation('move', readyPort.describe());
        } else for (const edge of EDGES) readyPort.syncDrawer(props.document.drawers[edge]);
        if (status === 'recovered') {
          const rebuiltLayout = readyPort.capture();
          props.runtime.syncDockviewLayout(rebuiltLayout, readyPort.describe());
          props.onDockviewLayoutChanged(rebuiltLayout);
        }
        setRestoreNotice(status === 'recovered'
          ? { state: 'empty', message: '布局快照无效，已根据工作区元数据重建。' }
          : null);
      },
      (error: unknown) => {
        setRestoreNotice({
          state: 'failed',
          message: error instanceof Error ? error.message : '工作区布局恢复失败',
        });
      },
    ).catch(error => { recordUiError(error, { reason: 'layout-operation' }); setRegionError(String(error)); });
  }, [props.document, props.edgeDrawers, props.onDockviewLayoutChanged, props.onDockviewReady, props.runtime]);

  useEffect(() => {
    if (!port || props.onRegionSplit) return;
    // Only commands write to Dockview. Native layout notifications are measured
    // results, not another resize request: feeding render snapshots back here
    // lets opposing edges repeatedly fight over the same available extent.
    return props.runtime.events.on('workbench.layout.changed@1', ({ operation }) => {
      if (operation !== 'drawer-change') return;
      for (const edge of EDGES) port.syncDrawer(props.runtime.getDrawer(edge));
    });
  }, [port, props.runtime, props.onRegionSplit]);

  useEffect(() => {
    const dismissPeek = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      const openPeekEdges = EDGES.filter((edge) => props.edgeDrawers.get(edge).mode === 'peek');
      props.edgeDrawers.dismissPeek();
      for (const edge of openPeekEdges) handleEdgeChanged(edge);
    };
    window.addEventListener('keydown', dismissPeek);
    return () => window.removeEventListener('keydown', dismissPeek);
  }, [handleEdgeChanged, props.edgeDrawers]);

  return (
    <RuntimeContext.Provider value={props.runtime}><RegionPullContext.Provider value={regionPull}>
      <main className={`forge-shell${hasWorkflowSidebar ? ' has-workflow-sidebar' : ''}`} data-workspace={props.document.workspaceId}
        onPointerDownCapture={event => {
          sashDrag.current = props.onRegionSplit && port && event.target instanceof Element && event.target.closest('.dv-sash:not(.dv-disabled)')
            ? { layout: port.capture(), collapsed: new Set(port.collapsedRegionIds()) } : null;
        }}
        onPointerUpCapture={() => {
          const started = sashDrag.current;
          if (!started || !port) return;
          sashDrag.current = null;
          // Complete native resizing first, then use ordinary close/dirty confirmation.
          requestAnimationFrame(() => { void (async () => {
            const closing = port.collapsedRegionIds().filter(id => !started.collapsed.has(id));
            const instances = closing.map(id => props.runtime.getInstance(id)).filter(instance => instance !== undefined);
            if (instances.some(instance => instance.locked) ||
                (instances.some(instance => instance.dirty) && !window.confirm('收起这些区域会关闭其中未保存的内容，仍要继续吗？'))) {
              port.restore(started.layout);
              return;
            }
            for (const id of closing) {
              if (props.runtime.getInstance(id)) await props.runtime.close(id, true);
            }
          })().catch(error => { recordUiError(error, { reason: 'layout-operation' }); setRegionError(String(error)); }); });
        }} onPointerCancelCapture={() => { sashDrag.current = null; }}>
        <div className="forge-dock-canvas">
          <DockviewReact
            className="dockview-theme-abyss"
            components={components}
            onReady={onReady}
            defaultRenderer="always"
            defaultTabComponent={ForgeEditorTab}
            autoHideEdgeGroups={!props.onRegionSplit}
            dockToEdgeGroups={!props.onRegionSplit}
            keyboardNavigation
            getTabContextMenuItems={() => []}
          />
        </div>
        {restoreNotice ? (
          <div className="forge-restore-notice">
            <EditorStateNotice state={restoreNotice.state} message={restoreNotice.message} />
          </div>
        ) : null}
        {regionError && <div className="forge-restore-notice" role="alert">{regionError}</div>}
        {!props.onRegionSplit && <><EdgeDrawerController
          coordinator={props.edgeDrawers}
          judgeMode={props.judgeMode}
          onFloatingRequest={props.onFloatingToolLibrary}
          onChanged={handleEdgeChanged}
        />
        <WindowMenu coordinator={props.edgeDrawers} onChanged={handleEdgeChanged} /></>}
      </main>
    </RegionPullContext.Provider></RuntimeContext.Provider>
  );
}

interface PanelParameters {
  instanceId: string;
  editorId: string;
}

function ForgeEditorPanel(props: IDockviewPanelProps<PanelParameters>): React.ReactElement {
  const runtime = requireRuntime();
  const minimalChrome = MINIMAL_CHROME_EDITORS.has(props.params.editorId);
  const workflowSidebar = WORKFLOW_SIDEBAR_EDITORS.has(props.params.editorId);
  useLayoutEffect(() => {
    const releases = [
      ...(minimalChrome ? [retainGroupClass(props.api.group.element, 'forge-minimal-chrome-group')] : []),
      ...(workflowSidebar ? [retainGroupClass(props.api.group.element, 'forge-workflow-sidebar-group')] : []),
    ];
    return () => { for (const release of releases) release(); };
  }, [minimalChrome, props.api.group.element, workflowSidebar]);
  const visibleCallback = useCallback(
    (visible: boolean) => runtime.updateVisibility(props.params.instanceId, visible),
    [props.params.instanceId, runtime],
  );
  const visible = usePanelVisibility(props.api, visibleCallback);
  const compact = usePanelCompact(props.api);
  return (
    <EditorErrorBoundary editorId={props.params.editorId}>
      <ForgeEditorHost instanceId={props.params.instanceId} visible={visible} compact={compact}
        minimalChrome={minimalChrome} workflowSidebar={workflowSidebar}
        getRegionBounds={() => props.api.group.element.getBoundingClientRect()} />
    </EditorErrorBoundary>
  );
}

function ForgeEditorHost({
  instanceId,
  visible,
  compact,
  minimalChrome,
  workflowSidebar,
  getRegionBounds,
}: {
  instanceId: string;
  visible: boolean;
  compact: boolean;
  minimalChrome: boolean;
  workflowSidebar: boolean;
  getRegionBounds(): DOMRect;
}): React.ReactElement {
  const runtime = requireRuntime();
  const [, refresh] = useState(0);
  const regionPull = useContext(RegionPullContext);
  useEffect(() => runtime.events.on('workbench.layout.changed@1', () => refresh(value => value + 1)), [runtime]);
  const instance = runtime.getInstance(instanceId);
  const definition = instance ? runtime.editors.get(instance.editorId) : undefined;
  const availability = instance ? runtime.editorAvailability(instance.editorId) : undefined;
  const [LoadedEditor, setLoadedEditor] = useState<React.ComponentType<EditorHostProps> | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    setLoadedEditor(null);
    setLoadError(null);
    if (!instance || availability?.status !== 'available') return;
    let current = true;
    runtime.loadEditor(instance.instanceId).then(
      (module) => {
        if (!current) return;
        if (!module) {
          setLoadError('编辑器加载失败，请重试。');
          return;
        }
        setLoadedEditor(() => module.default as React.ComponentType<EditorHostProps>);
      },
    );
    return () => { current = false; };
  }, [availability?.status, instance?.editorId, instance?.instanceId, loadAttempt, runtime]);

  if (!instance) return <EditorStateNotice state="disconnected" message="编辑器实例已断开。" />;
  if (!definition) return <EditorStateNotice state="failed" message="编辑器定义不可用。" />;
  const context = runtime.resolveContext(instance.instanceId);
  const header = createAreaHeaderContract(instance, context, visible, compact);
  const contentVisible = visible && !EDGES.some(edge => {
    const drawer = runtime.getDrawer(edge);
    return drawer.mode === 'hidden' && drawer.tabs.includes(instance.instanceId);
  });
  return (
    <div className={`forge-editor-layout${minimalChrome ? ' is-minimal-chrome' : ''}${workflowSidebar ? ' is-workflow-sidebar' : ''}`}
      data-instance-id={instanceId} inert={!contentVisible} aria-hidden={!contentVisible}>
      {regionPull && contentVisible && !workflowSidebar && <RegionPullHandles instanceId={instanceId} split={regionPull.split} collapse={regionPull.collapse} getBounds={getRegionBounds} />}
      {!minimalChrome && <AreaHeader
        contract={header}
        onAction={(action) => {
          if (action === 'close') {
            void requestClose(runtime, instance.instanceId);
            return;
          }
          runtime.onAreaAction(instance.instanceId, action);
        }}
      />}
      <div className="forge-editor-body">{availability && availability.status !== 'available' ? (
        <EditorStateNotice state={availability.status} message={availability.message ?? '编辑器暂不可用。'} />
      ) : loadError ? (
        <EditorStateNotice state="failed" message={loadError} retry={() => setLoadAttempt((value) => value + 1)} />
      ) : !LoadedEditor ? (
        <EditorStateNotice state="loading" message="正在加载编辑器…" />
      ) : <LoadedEditor
        instanceId={instance.instanceId}
        context={context}
        contextBinding={instance.contextBinding}
        localState={instance.localState}
        commands={runtime.commands}
        events={runtime.events}
        updateLocalState={(patch) => runtime.updateLocalState(instance.instanceId, patch)}
        close={() => { void requestClose(runtime, instance.instanceId); }}
        setTitle={(title) => runtime.setTitle(instance.instanceId, title)}
        suspended={!contentVisible && definition.renderPolicy === 'suspend-when-hidden'}
      />}</div>
    </div>
  );
}

function retainGroupClass(element: HTMLElement, className: string): () => void {
  const references = groupClassReferences.get(element) ?? new Map<string, number>();
  references.set(className, (references.get(className) ?? 0) + 1);
  groupClassReferences.set(element, references);
  element.classList.add(className);
  return () => {
    const current = groupClassReferences.get(element);
    if (!current) return;
    const remaining = (current.get(className) ?? 1) - 1;
    if (remaining > 0) {
      current.set(className, remaining);
      return;
    }
    current.delete(className);
    element.classList.remove(className);
    if (current.size === 0) groupClassReferences.delete(element);
  };
}

function ForgeEditorTab(props: IDockviewPanelHeaderProps<PanelParameters>): React.ReactElement {
  const runtime = requireRuntime();
  const instance = runtime.getInstance(props.params.instanceId);
  return (
    <DockviewDefaultTab
      {...props}
      hideClose={instance?.locked === true}
      closeActionOverride={() => { void requestClose(runtime, props.params.instanceId); }}
    />
  );
}

function WindowMenu({ coordinator, onChanged }: { coordinator: EdgeDrawerCoordinator; onChanged(edge: Edge): void }) {
  return (
    <details className="forge-window-menu">
      <summary>布局 ⌄</summary>
      <div className="forge-window-options"><p>展开或收起工作区域</p>
      {(Object.keys(EDGE_LABELS) as Edge[]).map((edge) => (
        <fieldset key={edge}>
          <legend>{EDGE_LABELS[edge]}</legend>
          <button type="button" onClick={() => { coordinator.setMode(edge, 'peek'); onChanged(edge); }}>临时展开</button>
          <button type="button" onClick={() => { coordinator.setMode(edge, 'pinned'); onChanged(edge); }}>固定</button>
          <button type="button" onClick={() => { coordinator.setMode(edge, 'hidden'); onChanged(edge); }}>隐藏</button>
        </fieldset>
      ))}</div>
    </details>
  );
}

function createAreaHeaderContract(
  instance: EditorInstance,
  context: WorkbenchContext,
  active: boolean,
  compact: boolean,
): AreaHeaderContract {
  return {
    height: 36,
    title: instance.title,
    contextSummary: summarizeContext(instance.contextBinding.mode === 'pinned'
      ? instance.contextBinding.context
      : context),
    mode: instance.executionMode,
    binding: instance.contextBinding,
    active,
    compact,
    actions: ['editor-menu', 'follow-pin', 'add', 'split', 'float', 'maximize-restore', 'more', 'close'],
  };
}

function EditorStateNotice({
  state,
  message,
  retry,
}: {
  state: EditorInstance['lifecycle'];
  message: string;
  retry?: () => void;
}) {
  return (
    <section className={`forge-editor-state is-${state}`} role={state === 'failed' ? 'alert' : 'status'}>
      <span>{message}</span>
      {retry ? <button type="button" onClick={retry}>重试</button> : null}
    </section>
  );
}

class EditorErrorBoundary extends Component<
  React.PropsWithChildren<{ editorId: string }>,
  { error: Error | null }
> {
  override state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  override componentDidCatch(error: Error) {
    recordUiError(error, { editorId: this.props.editorId, phase: 'error', reason: 'error-boundary' });
  }

  override componentDidUpdate(previous: Readonly<React.PropsWithChildren<{ editorId: string }>>) {
    if (previous.editorId !== this.props.editorId && this.state.error) this.setState({ error: null });
  }

  override render() {
    if (this.state.error) {
      return (
        <EditorStateNotice
          state="failed"
          message={`${this.props.editorId} 渲染失败：${this.state.error.message}`}
          retry={() => this.setState({ error: null })}
        />
      );
    }
    return this.props.children;
  }
}

function usePanelCompact(api: IDockviewPanelProps<PanelParameters>['api']): boolean {
  const [compact, setCompact] = useState(api.width > 0 && api.width < 900);
  useEffect(() => {
    const disposable = api.onDidDimensionsChange(({ width }) => setCompact(width < 900));
    return () => disposable.dispose();
  }, [api]);
  return compact;
}

async function requestClose(runtime: ForgeShellRuntime, instanceId: string): Promise<void> {
  const result = await runtime.close(instanceId, false);
  if (result.status !== 'confirmation-required') return;
  if (window.confirm('此编辑器包含未保存更改。仍要关闭吗？')) await runtime.close(instanceId, true);
}

function summarizeContext(context: Partial<WorkbenchContext>): string {
  const parts = [
    context.sceneId ? `场景 ${context.sceneId}` : null,
    context.activeFeatureId ? `功能 ${context.activeFeatureId}` : null,
    context.selectedAssetIds?.length ? `${context.selectedAssetIds.length} 个资产` : null,
  ].filter((part): part is string => part !== null);
  return parts.length > 0 ? parts.join(' · ') : '全局上下文';
}

function requireRuntime(): ForgeShellRuntime {
  const runtime = useContext(RuntimeContext);
  if (!runtime) throw new Error('ForgeShell runtime is unavailable');
  return runtime;
}

const EDGE_LABELS: Record<Edge, string> = { left: '左侧工具', right: '右侧工具', top: '顶部工具', bottom: '底部工具' };
const EDGES: Edge[] = ['left', 'right', 'top', 'bottom'];
