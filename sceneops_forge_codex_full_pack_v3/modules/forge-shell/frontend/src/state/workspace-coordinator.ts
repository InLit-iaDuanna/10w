import type {
  AreaState,
  CommandSource,
  ContextBinding,
  DockingEnginePort,
  DockingMutationKind,
  DockingTopology,
  DrawerState,
  EditorAvailability,
  EditorInstance,
  EditorLifecycle,
  EditorPlacement,
  EditorRegionState,
  FloatingBounds,
  JsonValue,
  LazyEditorModule,
  WorkspaceDocument,
} from '../contracts.ts';
import type { WorkbenchEventBus } from '../events/workbench-event-bus.ts';
import type { EditorEnvironment, EditorRegistry } from './editor-registry.ts';
import type { WorkspaceRegistry } from './workspace-registry.ts';
import {
  createWorkspaceFromPreset,
  randomIdentifier,
  type IdentifierFactory,
} from './workspace-factory.ts';
import type {
  CloseEditorResult,
  LayoutMutationAuthorization,
  LayoutMutationResult,
  OpenEditorRequest,
  OpenEditorResult,
} from './workspace-operations.ts';

interface WorkspaceHistoryFrame {
  document: WorkspaceDocument;
  closed: EditorInstance[];
}

interface MoveEditorOptions extends LayoutMutationAuthorization {
  forceReplaceDirty?: boolean;
}

interface LocatedContainer {
  kind: 'grid' | 'drawer' | 'floating' | 'popout';
  container: { tabs: string[]; activeInstanceId: string | null };
  index?: number;
  bounds?: FloatingBounds;
}

export class WorkspaceCoordinator {
  readonly #editors: EditorRegistry;
  readonly #workspaces: WorkspaceRegistry;
  readonly #events: WorkbenchEventBus;
  readonly #engine: DockingEnginePort;
  readonly #environment: EditorEnvironment;
  readonly #createId: IdentifierFactory;
  readonly #history: WorkspaceHistoryFrame[] = [];
  readonly #closed: EditorInstance[] = [];
  #pendingDockviewMutation: (
    WorkspaceHistoryFrame & { kind: DockingMutationKind; topology: DockingTopology }
  ) | null = null;
  #document: WorkspaceDocument;

  constructor(options: {
    document: WorkspaceDocument;
    editors: EditorRegistry;
    workspaces: WorkspaceRegistry;
    events: WorkbenchEventBus;
    engine: DockingEnginePort;
    environment: EditorEnvironment;
    createId?: IdentifierFactory;
  }) {
    this.#document = clone(options.document);
    this.#editors = options.editors;
    this.#workspaces = options.workspaces;
    this.#events = options.events;
    this.#engine = options.engine;
    this.#environment = options.environment;
    this.#createId = options.createId ?? randomIdentifier;
  }

  snapshot(): WorkspaceDocument {
    const document = clone(this.#document);
    document.dockviewLayout = clone(this.#engine.capture());
    return document;
  }

  historyDepth(): number {
    return this.#history.length;
  }

  isCustomized(): boolean {
    return this.#document.customized;
  }

  getInstance(instanceId: string): EditorInstance | undefined {
    const instance = this.#document.instances[instanceId];
    return instance ? clone(instance) : undefined;
  }

  getDrawer(edge: DrawerState['edge']): DrawerState {
    return clone(this.#document.drawers[edge]);
  }

  editorAvailability(editorId: string): EditorAvailability {
    return this.#editors.availability(editorId, this.#environment);
  }

  async openEditor(request: OpenEditorRequest): Promise<OpenEditorResult> {
    const definition = this.#editors.get(request.editorId);
    const availability = this.#editors.availability(request.editorId, this.#environment);
    if (availability.status !== 'available') return { status: 'unavailable', availability };
    const existing = definition.singleton ? this.#findEditor(request.editorId) : undefined;
    if (existing) {
      if (request.placement?.mode === 'replace' && request.placement.relativeToInstanceId
          && request.placement.relativeToInstanceId !== existing.instanceId) {
        const moved = await this.moveEditor(existing.instanceId, request.placement, {
          source: request.source, confirmed: request.confirmed, forceReplaceDirty: request.forceReplaceDirty,
        });
        if (moved.status !== 'completed') return moved;
      }
      await this.#engine.focus(existing.instanceId);
      return { status: 'focused', instance: clone(existing) };
    }
    if (request.source === 'assistant' && this.#document.customized) {
      return { status: 'confirmation-required', reason: 'assistant-layout-change' };
    }
    const placement = this.#resolvePlacement(request.placement ?? definition.defaultPlacement);
    const replaced = this.#replacementTarget(placement);
    if (replaced?.locked) return { status: 'rejected', reason: 'locked-editor' };
    if (replaced?.dirty && !request.forceReplaceDirty && !request.confirmed) {
      return { status: 'confirmation-required', reason: 'unsaved-editor' };
    }
    const executionMode = request.source === 'workflow' && request.executionMode
      ? request.executionMode
      : 'live';
    const instance = this.#createInstance(request.editorId, executionMode);
    const before = this.snapshot();
    const opened = await this.#engine.open(clone(instance), placement);
    if (opened === false) return { status: 'unavailable', code: 'POPOUT_BLOCKED' };
    this.#remember(before);
    if (replaced) {
      this.#substituteInstance(replaced.instanceId, instance);
      this.#closed.push(clone(replaced));
    } else {
      this.#place(instance, placement);
    }
    this.#adoptCompleteEngineTopology();
    this.#document.customized = true;
    this.#emitLayout('open-editor');
    this.#events.emit('workbench.editor.opened@1', {
      instance: clone(instance),
      placement,
      source: request.source,
    });
    return { status: 'opened', instance: clone(instance) };
  }

  async closeEditor(
    instanceId: string,
    authorization: boolean | LayoutMutationAuthorization = false,
  ): Promise<CloseEditorResult> {
    const resolved = normalizeAuthorization(authorization);
    const assistantGuard = this.#assistantGuard(resolved.source);
    if (assistantGuard) return assistantGuard;
    const instance = this.#document.instances[instanceId];
    if (!instance) return { status: 'rejected', reason: 'unknown-editor' };
    if (instance.locked) return { status: 'rejected', reason: 'locked-editor' };
    if (instance.dirty && !resolved.confirmed) {
      return { status: 'confirmation-required', reason: 'unsaved-editor' };
    }
    const before = this.snapshot();
    await this.#engine.close(instanceId);
    this.#remember(before);
    this.#removeInstance(instanceId);
    this.#closed.push(clone(instance));
    this.#adoptCompleteEngineTopology();
    this.#document.customized = true;
    this.#events.emit('workbench.editor.closed@1', { instance: clone(instance) });
    this.#emitLayout('close-editor');
    return { status: 'closed', instance: clone(instance) };
  }

  async reopenEditor(source: OpenEditorRequest['source'] = 'menu'): Promise<OpenEditorResult | { status: 'empty' }> {
    const assistantGuard = this.#assistantGuard(source);
    if (assistantGuard) return assistantGuard;
    const instance = this.#closed.at(-1);
    if (!instance) return { status: 'empty' };
    const placement = this.#resolvePlacement({ mode: 'tab' });
    const before = this.snapshot();
    const opened = await this.#engine.open(clone(instance), placement);
    if (opened === false) return { status: 'unavailable', code: 'POPOUT_BLOCKED' };
    this.#remember(before, this.#closed);
    this.#closed.pop();
    this.#place(instance, placement);
    this.#adoptCompleteEngineTopology();
    this.#document.customized = true;
    this.#events.emit('workbench.editor.opened@1', { instance: clone(instance), placement, source });
    this.#emitLayout('reopen-editor');
    return { status: 'opened', instance: clone(instance) };
  }

  async moveEditor(
    instanceId: string,
    placement: EditorPlacement,
    options: MoveEditorOptions = { source: 'button' },
  ): Promise<LayoutMutationResult> {
    const assistantGuard = this.#assistantGuard(options.source);
    if (assistantGuard) return assistantGuard;
    const instance = this.#requireInstance(instanceId);
    const resolvedPlacement = this.#resolvePlacement(placement, instanceId);
    if (instance.locked) return { status: 'rejected', reason: 'locked-editor' };
    if (requiresRelativeTarget(resolvedPlacement) &&
        (!resolvedPlacement.relativeToInstanceId ||
          resolvedPlacement.relativeToInstanceId === instanceId ||
          !this.#document.instances[resolvedPlacement.relativeToInstanceId])) {
      return { status: 'rejected', reason: 'invalid-docking-mutation' };
    }
    const replaced = this.#replacementTarget(resolvedPlacement, instanceId);
    if (replaced?.locked) return { status: 'rejected', reason: 'locked-editor' };
    if (replaced?.dirty && !options.forceReplaceDirty && !options.confirmed) {
      return { status: 'confirmation-required', reason: 'unsaved-editor' };
    }
    const before = this.snapshot();
    const moved = await this.#engine.move(clone(instance), resolvedPlacement);
    if (moved === false) throw new Error('Dockview could not complete the requested move');
    this.#remember(before);
    this.#removeFromContainers(instanceId);
    if (replaced) {
      this.#substituteInstance(replaced.instanceId, instance);
      this.#closed.push(clone(replaced));
    } else {
      this.#placeExisting(instance, resolvedPlacement);
    }
    this.#adoptCompleteEngineTopology();
    this.#document.customized = true;
    this.#emitLayout('move-editor');
    return { status: 'completed' };
  }

  async joinAreas(
    sourceAreaId: string,
    targetAreaId: string,
    authorization: LayoutMutationAuthorization = { source: 'button' },
  ): Promise<LayoutMutationResult> {
    const assistantGuard = this.#assistantGuard(authorization.source);
    if (assistantGuard) return assistantGuard;
    if (sourceAreaId === targetAreaId) return { status: 'completed' };
    const source = this.#document.areas.find((area) => area.areaId === sourceAreaId);
    const target = this.#document.areas.find((area) => area.areaId === targetAreaId);
    if (!source || !target) throw new Error('Unknown source or target area');
    const sourceInstanceId = source.activeInstanceId ?? source.tabs[0];
    const targetInstanceId = target.activeInstanceId ?? target.tabs[0];
    if (!sourceInstanceId || !targetInstanceId) throw new Error('Cannot join empty areas');
    if (source.tabs.some((id) => this.#document.instances[id]?.locked)) {
      return { status: 'rejected', reason: 'locked-editor' };
    }
    const before = this.snapshot();
    await this.#engine.join(sourceInstanceId, targetInstanceId);
    this.#remember(before);
    for (const instanceId of source.tabs) if (!target.tabs.includes(instanceId)) target.tabs.push(instanceId);
    target.activeInstanceId = source.activeInstanceId ?? target.activeInstanceId;
    this.#document.areas = this.#document.areas.filter((area) => area.areaId !== sourceAreaId);
    this.#adoptCompleteEngineTopology();
    this.#document.customized = true;
    this.#emitLayout('join-areas');
    return { status: 'completed' };
  }

  async switchEditor(
    instanceId: string,
    editorId: string,
    authorization: LayoutMutationAuthorization = { source: 'button' },
  ): Promise<OpenEditorResult> {
    const assistantGuard = this.#assistantGuard(authorization.source);
    if (assistantGuard) return assistantGuard;
    const current = this.#requireInstance(instanceId);
    if (current.locked) return { status: 'rejected', reason: 'locked-editor' };
    if (current.dirty && !authorization.confirmed) {
      return { status: 'confirmation-required', reason: 'unsaved-editor' };
    }
    const availability = this.#editors.availability(editorId, this.#environment);
    if (availability.status !== 'available') return { status: 'unavailable', availability };
    const definition = this.#editors.get(editorId);
    const existing = definition.singleton ? this.#findEditor(editorId) : undefined;
    if (existing && existing.instanceId !== instanceId) {
      return this.openEditor({ editorId, placement: { mode: 'replace', relativeToInstanceId: instanceId },
        source: authorization.source, confirmed: authorization.confirmed });
    }
    const next: EditorInstance = {
      ...current,
      editorId,
      title: definition.title,
      localState: clone(definition.initialState()),
      dirty: false,
      lifecycle: 'loading',
    };
    const before = this.snapshot();
    await this.#engine.switchEditor(clone(next));
    this.#remember(before);
    this.#document.instances[instanceId] = next;
    this.#document.customized = true;
    this.#emitLayout('switch-editor');
    return { status: 'opened', instance: clone(next) };
  }

  async toggleMaximize(
    areaId: string,
    authorization: LayoutMutationAuthorization = { source: 'button' },
  ): Promise<LayoutMutationResult> {
    const assistantGuard = this.#assistantGuard(authorization.source);
    if (assistantGuard) return assistantGuard;
    const area = this.#document.areas.find((candidate) => candidate.areaId === areaId);
    if (!area) throw new Error(`Unknown area: ${areaId}`);
    const next = this.#document.maximizedAreaId === areaId ? null : areaId;
    const before = this.snapshot();
    await this.#engine.maximize(next ? area.activeInstanceId : null);
    this.#remember(before);
    this.#document.maximizedAreaId = next;
    this.#adoptCompleteEngineTopology();
    this.#document.customized = true;
    this.#emitLayout(next ? 'maximize-area' : 'restore-area');
    return { status: 'completed' };
  }

  setDirty(instanceId: string, dirty: boolean): void {
    this.#requireInstance(instanceId).dirty = dirty;
    this.#emitLayout('editor-dirty');
  }

  setLifecycle(instanceId: string, lifecycle: EditorLifecycle): void {
    this.#requireInstance(instanceId).lifecycle = lifecycle;
  }

  setContextBinding(instanceId: string, binding: ContextBinding): void {
    this.#requireInstance(instanceId).contextBinding = clone(binding);
    this.#events.emit('workbench.context.binding_changed@1', { instanceId, binding: clone(binding) });
    this.#emitLayout('context-binding');
  }

  async loadEditor(instanceId: string): Promise<LazyEditorModule | null> {
    const instance = this.#requireInstance(instanceId);
    instance.lifecycle = 'loading';
    try {
      const module = await this.#editors.load(instance.editorId);
      instance.lifecycle = 'ready';
      return module;
    } catch (error) {
      instance.lifecycle = 'failed';
      this.#events.emit('workbench.editor.load_failed@1', {
        instanceId,
        editorId: instance.editorId,
        code: 'EDITOR_LOAD_FAILED',
        message: error instanceof Error ? error.message : 'Editor failed to load',
      });
      return null;
    }
  }

  async undo(): Promise<boolean> {
    const previous = this.#history.at(-1);
    if (!previous) return false;
    await this.#engine.restore(clone(previous.document.dockviewLayout));
    this.#history.pop();
    this.#document = clone(previous.document);
    this.#closed.splice(0, this.#closed.length, ...clone(previous.closed));
    this.#emitLayout('undo');
    return true;
  }

  async reset(
    presetId: string,
    authorization: LayoutMutationAuthorization = { source: 'button' },
  ): Promise<LayoutMutationResult> {
    const assistantGuard = this.#assistantGuard(authorization.source);
    if (assistantGuard) return assistantGuard;
    const preset = this.#workspaces.get(presetId);
    const judgeSelfReset = preset.judgeMode === true && presetId === this.#document.workspaceId;
    if (!judgeSelfReset && !authorization.confirmed &&
        Object.values(this.#document.instances).some((instance) => instance.dirty)) {
      return { status: 'confirmation-required', reason: 'unsaved-editor' };
    }
    const next = createWorkspaceFromPreset(preset, this.#editors, this.#createId);
    const before = this.snapshot();
    try {
      await this.#engine.restore(next.dockviewLayout);
      const instances = Object.values(next.instances);
      for (const [index, contribution] of preset.editors.entries()) {
        const instance = instances[index];
        if (!instance) continue;
        const opened = await this.#engine.open(clone(instance), contribution.placement);
        if (opened === false) throw new Error(`Preset popout was blocked: ${preset.id}`);
      }
    } catch (error) {
      await this.#engine.restore(before.dockviewLayout);
      throw error;
    }
    next.dockviewLayout = clone(this.#engine.capture());
    this.#remember(before);
    this.#document = next;
    this.#closed.length = 0;
    this.#adoptCompleteEngineTopology();
    this.#emitLayout(preset.judgeMode ? 'judge-reset' : 'workspace-reset');
    return { status: 'completed' };
  }

  beginDockviewMutation(kind: DockingMutationKind): void {
    if (this.#pendingDockviewMutation) return;
    this.#pendingDockviewMutation = {
      kind,
      document: this.snapshot(),
      closed: clone(this.#closed),
      topology: this.#engine.describe(),
    };
  }

  async completeDockviewMutation(
    kind: DockingMutationKind,
    topology: DockingTopology,
  ): Promise<LayoutMutationResult> {
    const pending = this.#pendingDockviewMutation;
    this.#pendingDockviewMutation = null;
    if (!pending) return { status: 'rejected', reason: 'invalid-docking-mutation' };

    const ids = topology.groups.flatMap((group) => group.tabs);
    if (new Set(ids).size !== ids.length || ids.some((id) => !pending.document.instances[id])) {
      this.#document = clone(pending.document);
      this.#closed.splice(0, this.#closed.length, ...clone(pending.closed));
      await this.#engine.restore(pending.document.dockviewLayout);
      return { status: 'rejected', reason: 'invalid-docking-mutation' };
    }
    const removed = Object.values(pending.document.instances).filter(
      (instance) => !ids.includes(instance.instanceId),
    );
    if (removed.some((instance) => instance.locked)) {
      this.#document = clone(pending.document);
      this.#closed.splice(0, this.#closed.length, ...clone(pending.closed));
      await this.#engine.restore(pending.document.dockviewLayout);
      return { status: 'rejected', reason: 'locked-editor' };
    }
    const lockedMoved = Object.values(pending.document.instances).some((instance) => {
      if (!instance.locked) return false;
      return topologyGroupKey(pending.topology, instance.instanceId) !==
        topologyGroupKey(topology, instance.instanceId);
    });
    if (lockedMoved) {
      this.#document = clone(pending.document);
      this.#closed.splice(0, this.#closed.length, ...clone(pending.closed));
      await this.#engine.restore(pending.document.dockviewLayout);
      return { status: 'rejected', reason: 'locked-editor' };
    }
    if (removed.some((instance) => instance.dirty)) {
      this.#document = clone(pending.document);
      this.#closed.splice(0, this.#closed.length, ...clone(pending.closed));
      await this.#engine.restore(pending.document.dockviewLayout);
      return { status: 'confirmation-required', reason: 'unsaved-editor' };
    }

    this.#remember(pending.document, pending.closed);
    this.#document = clone(pending.document);
    for (const instance of removed) {
      delete this.#document.instances[instance.instanceId];
      this.#closed.push(clone(instance));
      this.#events.emit('workbench.editor.closed@1', { instance: clone(instance) });
    }
    this.#applyTopology(topology);
    this.#document.dockviewLayout = clone(this.#engine.capture());
    this.#document.customized = true;
    const mutationKind = pending.kind === kind ? kind : `${pending.kind}-${kind}`;
    this.#emitLayout(`dockview-${mutationKind}`);
    return { status: 'completed' };
  }

  syncDockviewLayout(layout: JsonValue, topology: DockingTopology): void {
    this.#document.dockviewLayout = clone(layout);
    const activeGroup = topology.groups.find((group) => group.tabs.includes(topology.activeInstanceId ?? ''));
    const activeArea = activeGroup?.location === 'grid'
      ? this.#document.areas.find((area) => area.tabs.some((id) => activeGroup.tabs.includes(id)))
      : undefined;
    this.#document.activeAreaId = activeArea?.areaId ?? this.#document.activeAreaId;
    const maximizedGroup = topology.groups.find((group) => group.tabs.includes(topology.maximizedInstanceId ?? ''));
    this.#document.maximizedAreaId = maximizedGroup
      ? this.#areaIdForTabs(maximizedGroup.tabs)
      : null;
    for (const group of topology.groups) {
      this.#syncActiveTab(group.tabs, group.activeInstanceId);
      if (group.location === 'floating') this.#syncFloatingBounds(group);
      if (group.location === 'popout') this.#syncPopoutBounds(group);
      if (group.location === 'edge' && group.edge) this.#syncDrawerFromTopology(group);
    }
    this.#emitLayout('dockview-layout');
  }

  #remember(document: WorkspaceDocument, closed: EditorInstance[] = this.#closed): void {
    this.#history.push({ document: clone(document), closed: clone(closed) });
    if (this.#history.length > 50) this.#history.shift();
  }

  #createInstance(editorId: string, executionMode: EditorInstance['executionMode']): EditorInstance {
    const definition = this.#editors.get(editorId);
    return {
      instanceId: this.#createId('instance'),
      editorId,
      title: definition.title,
      localState: clone(definition.initialState()),
      contextBinding: { mode: 'follow-global' },
      dirty: false,
      locked: false,
      lifecycle: 'loading',
      executionMode,
      regions: [],
    };
  }

  updateLocalState(instanceId: string, localState: JsonValue, dirty = true): void {
    const instance = this.#requireInstance(instanceId);
    instance.localState = clone(localState);
    instance.dirty = dirty;
    this.#emitLayout('editor-state');
  }

  setTitle(instanceId: string, title: string): void {
    this.#requireInstance(instanceId).title = title;
    this.#emitLayout('editor-title');
  }

  upsertRegion(instanceId: string, region: EditorRegionState): void {
    const instance = this.#requireInstance(instanceId);
    const index = instance.regions.findIndex((candidate) => candidate.regionId === region.regionId);
    if (index === -1) instance.regions.push(clone(region));
    else instance.regions[index] = clone(region);
    this.#emitLayout('editor-region');
  }

  removeRegion(instanceId: string, regionId: string): void {
    const instance = this.#requireInstance(instanceId);
    instance.regions = instance.regions.filter((region) => region.regionId !== regionId);
    this.#emitLayout('editor-region');
  }

  syncDrawer(drawer: DrawerState): void {
    const current = this.#document.drawers[drawer.edge];
    if (JSON.stringify(current) === JSON.stringify(drawer)) return;
    this.#remember(this.snapshot());
    this.#document.drawers[drawer.edge] = clone(drawer);
    this.#document.customized = true;
    this.#emitLayout('drawer-change');
  }

  #place(instance: EditorInstance, placement: EditorPlacement): void {
    this.#document.instances[instance.instanceId] = instance;
    this.#placeExisting(instance, placement);
  }

  #placeExisting(instance: EditorInstance, placement: EditorPlacement): void {
    if (placement.mode === 'drawer') {
      const drawer = this.#document.drawers[placement.edge];
      drawer.tabs.push(instance.instanceId);
      drawer.activeInstanceId = instance.instanceId;
      return;
    }
    if (placement.mode === 'floating' || placement.mode === 'popout') {
      const area = this.#newArea(instance.instanceId);
      const bounds = placement.bounds ?? { left: 80, top: 80, width: 640, height: 420 };
      if (placement.mode === 'floating') {
        this.#document.floatingGroups.push({ groupId: this.#createId('floating'), area, bounds });
      } else {
        this.#document.popoutGroups.push({ groupId: this.#createId('popout'), area, bounds, blocked: false });
      }
      return;
    }
    const target = this.#targetContainer(placement.relativeToInstanceId);
    if (placement.mode === 'split') {
      const area = this.#newArea(instance.instanceId);
      const before = placement.direction === 'left' || placement.direction === 'above';
      if (target?.kind === 'floating') {
        this.#document.floatingGroups.push({
          groupId: this.#createId('floating'),
          area,
          bounds: clone(target.bounds ?? DEFAULT_BOUNDS),
        });
      } else if (target?.kind === 'popout') {
        this.#document.popoutGroups.push({
          groupId: this.#createId('popout'),
          area,
          bounds: clone(target.bounds ?? DEFAULT_BOUNDS),
          blocked: false,
        });
      } else if (target?.kind === 'drawer') {
        target.container.tabs.push(instance.instanceId);
        target.container.activeInstanceId = instance.instanceId;
      } else {
        const targetIndex = target?.index ?? this.#document.areas.length;
        this.#document.areas.splice(before ? targetIndex : targetIndex + (target ? 1 : 0), 0, area);
        this.#document.activeAreaId = area.areaId;
      }
      return;
    }
    if (!target) {
      const area = this.#newArea(instance.instanceId);
      this.#document.areas.push(area);
      this.#document.activeAreaId = area.areaId;
      return;
    }
    if (placement.mode === 'replace') {
      target.container.tabs = target.container.tabs.filter((id) => id !== target.container.activeInstanceId);
    }
    target.container.tabs.push(instance.instanceId);
    target.container.activeInstanceId = instance.instanceId;
    if (target.kind === 'grid') {
      const area = target.container as AreaState;
      this.#document.activeAreaId = area.areaId;
    }
  }

  #newArea(instanceId: string) {
    return {
      areaId: this.#createId('area'),
      tabs: [instanceId],
      activeInstanceId: instanceId,
      headerPosition: 'top' as const,
    };
  }

  #resolvePlacement(placement: EditorPlacement, movingInstanceId?: string): EditorPlacement {
    if (placement.mode === 'drawer' || placement.mode === 'floating' || placement.mode === 'popout' ||
        placement.relativeToInstanceId) return placement;
    const topology = this.#engine.describe();
    const liveActive = topology.activeInstanceId;
    const documentActive = this.#document.areas.find(
      (area) => area.areaId === this.#document.activeAreaId,
    )?.activeInstanceId;
    const alternateLiveGroup = topology.groups.find(
      (group) => !group.tabs.includes(movingInstanceId ?? '') && group.tabs.length > 0,
    );
    const differentLiveGroup = alternateLiveGroup?.activeInstanceId ?? alternateLiveGroup?.tabs[0];
    const anyLiveAlternative = topology.groups.flatMap((group) => group.tabs).find(
      (instanceId) => instanceId !== movingInstanceId,
    );
    const located = this.#locatedContainers();
    const movingContainer = located.find(({ container }) => container.tabs.includes(movingInstanceId ?? ''));
    const differentDocumentContainer = located.find(
      ({ container }) => container !== movingContainer?.container && container.tabs.length > 0,
    )?.container;
    const anyDocumentAlternative = located.flatMap(({ container }) => container.tabs).find(
      (instanceId) => instanceId !== movingInstanceId,
    );
    const relativeToInstanceId = [
      liveActive,
      differentLiveGroup,
      documentActive,
      differentDocumentContainer?.activeInstanceId,
      differentDocumentContainer?.tabs[0],
      anyLiveAlternative,
      anyDocumentAlternative,
    ].find(
      (instanceId): instanceId is string => Boolean(
        instanceId && instanceId !== movingInstanceId && this.#document.instances[instanceId],
      ),
    );
    return relativeToInstanceId ? { ...placement, relativeToInstanceId } : placement;
  }

  #targetContainer(relativeToInstanceId?: string): LocatedContainer | undefined {
    const located = this.#locatedContainers();
    if (relativeToInstanceId) {
      return located.find(({ container }) => container.tabs.includes(relativeToInstanceId));
    }
    return located.find(({ kind, container }) =>
      kind === 'grid' && (container as AreaState).areaId === this.#document.activeAreaId,
    ) ?? located.find(({ kind }) => kind === 'grid');
  }

  #replacementTarget(placement: EditorPlacement, movingInstanceId?: string): EditorInstance | undefined {
    if (placement.mode !== 'replace') return undefined;
    if (placement.relativeToInstanceId && placement.relativeToInstanceId !== movingInstanceId) {
      return this.#document.instances[placement.relativeToInstanceId];
    }
    const target = this.#targetContainer(placement.relativeToInstanceId);
    return target?.container.activeInstanceId && target.container.activeInstanceId !== movingInstanceId
      ? this.#document.instances[target.container.activeInstanceId]
      : undefined;
  }

  #substituteInstance(targetInstanceId: string, replacement: EditorInstance): void {
    const container = this.#allContainers().find((candidate) => candidate.tabs.includes(targetInstanceId));
    if (!container) throw new Error(`Cannot replace unplaced editor: ${targetInstanceId}`);
    const index = container.tabs.indexOf(targetInstanceId);
    container.tabs[index] = replacement.instanceId;
    if (container.activeInstanceId === targetInstanceId) container.activeInstanceId = replacement.instanceId;
    delete this.#document.instances[targetInstanceId];
    this.#document.instances[replacement.instanceId] = replacement;
  }

  #findEditor(editorId: string): EditorInstance | undefined {
    return Object.values(this.#document.instances).find((instance) => instance.editorId === editorId);
  }

  #requireInstance(instanceId: string): EditorInstance {
    const instance = this.#document.instances[instanceId];
    if (!instance) throw new Error(`Unknown editor instance: ${instanceId}`);
    return instance;
  }

  #removeInstance(instanceId: string): void {
    this.#removeFromContainers(instanceId);
    delete this.#document.instances[instanceId];
  }

  #removeFromContainers(instanceId: string): void {
    for (const area of this.#document.areas) removeTab(area, instanceId);
    for (const drawer of Object.values(this.#document.drawers)) removeTab(drawer, instanceId);
    for (const group of this.#document.floatingGroups) removeTab(group.area, instanceId);
    for (const group of this.#document.popoutGroups) removeTab(group.area, instanceId);
    this.#document.areas = this.#document.areas.filter((area) => area.tabs.length > 0);
    this.#document.floatingGroups = this.#document.floatingGroups.filter((group) => group.area.tabs.length > 0);
    this.#document.popoutGroups = this.#document.popoutGroups.filter((group) => group.area.tabs.length > 0);
    if (!this.#document.areas.some((area) => area.areaId === this.#document.activeAreaId)) {
      this.#document.activeAreaId = this.#document.areas[0]?.areaId ?? null;
    }
  }

  #allContainers(): Array<{ tabs: string[]; activeInstanceId: string | null }> {
    return this.#locatedContainers().map(({ container }) => container);
  }

  #locatedContainers(): LocatedContainer[] {
    return [
      ...this.#document.areas.map((container, index) => ({ kind: 'grid' as const, container, index })),
      ...Object.values(this.#document.drawers).map((container) => ({ kind: 'drawer' as const, container })),
      ...this.#document.floatingGroups.map((group) => ({
        kind: 'floating' as const,
        container: group.area,
        bounds: group.bounds,
      })),
      ...this.#document.popoutGroups.map((group) => ({
        kind: 'popout' as const,
        container: group.area,
        bounds: group.bounds,
      })),
    ];
  }

  #areaIdForTabs(tabs: string[]): string | null {
    const area = [
      ...this.#document.areas,
      ...this.#document.floatingGroups.map((group) => group.area),
      ...this.#document.popoutGroups.map((group) => group.area),
    ].find((candidate) => candidate.tabs.some((instanceId) => tabs.includes(instanceId)));
    return area?.areaId ?? null;
  }

  #assistantGuard(
    source: CommandSource,
  ): { status: 'confirmation-required'; reason: 'assistant-layout-change' } | null {
    return source === 'assistant' && this.#document.customized
      ? { status: 'confirmation-required', reason: 'assistant-layout-change' }
      : null;
  }

  #adoptCompleteEngineTopology(): boolean {
    const topology = this.#engine.describe();
    const topologyIds = topology.groups.flatMap((group) => group.tabs);
    const documentIds = Object.keys(this.#document.instances);
    if (topologyIds.length !== documentIds.length ||
        new Set(topologyIds).size !== topologyIds.length ||
        topologyIds.some((instanceId) => !this.#document.instances[instanceId])) {
      return false;
    }
    this.#applyTopology(topology);
    this.#document.dockviewLayout = clone(this.#engine.capture());
    return true;
  }

  #applyTopology(topology: DockingTopology): void {
    const priorFloating = new Map(this.#document.floatingGroups.map((group) => [group.groupId, group]));
    const priorPopouts = new Map(this.#document.popoutGroups.map((group) => [group.groupId, group]));
    this.#document.areas = [];
    this.#document.floatingGroups = [];
    this.#document.popoutGroups = [];
    for (const drawer of Object.values(this.#document.drawers)) {
      drawer.tabs = [];
      drawer.activeInstanceId = null;
    }
    for (const group of topology.groups) {
      const area = {
        areaId: group.location === 'grid' ? group.groupId : `${group.groupId}:area`,
        tabs: [...group.tabs],
        activeInstanceId: group.activeInstanceId,
        headerPosition: group.headerPosition,
      };
      if (group.location === 'grid') {
        this.#document.areas.push(area);
      } else if (group.location === 'floating') {
        this.#document.floatingGroups.push({
          groupId: group.groupId,
          area,
          bounds: clone(group.bounds ?? priorFloating.get(group.groupId)?.bounds ?? DEFAULT_BOUNDS),
        });
      } else if (group.location === 'popout') {
        this.#document.popoutGroups.push({
          groupId: group.groupId,
          area,
          bounds: clone(group.bounds ?? priorPopouts.get(group.groupId)?.bounds ?? DEFAULT_BOUNDS),
          blocked: false,
        });
      } else if (group.edge) {
        const drawer = this.#document.drawers[group.edge];
        drawer.tabs = [...group.tabs];
        drawer.activeInstanceId = group.activeInstanceId;
        this.#syncDrawerFromTopology(group);
      }
    }
    const activeGroup = topology.groups.find((group) => group.tabs.includes(topology.activeInstanceId ?? ''));
    this.#document.activeAreaId = activeGroup?.location === 'grid' ? activeGroup.groupId : null;
    const maximizedGroup = topology.groups.find((group) => group.tabs.includes(topology.maximizedInstanceId ?? ''));
    this.#document.maximizedAreaId = maximizedGroup
      ? maximizedGroup.location === 'grid'
        ? maximizedGroup.groupId
        : `${maximizedGroup.groupId}:area`
      : null;
  }

  #syncFloatingBounds(topology: DockingTopology['groups'][number]): void {
    if (!topology.bounds) return;
    const group = this.#document.floatingGroups.find((candidate) =>
      candidate.groupId === topology.groupId || candidate.area.tabs.some((id) => topology.tabs.includes(id)),
    );
    if (group) group.bounds = clone(topology.bounds);
  }

  #syncPopoutBounds(topology: DockingTopology['groups'][number]): void {
    if (!topology.bounds) return;
    const group = this.#document.popoutGroups.find((candidate) =>
      candidate.groupId === topology.groupId || candidate.area.tabs.some((id) => topology.tabs.includes(id)),
    );
    if (group) group.bounds = clone(topology.bounds);
  }

  #syncActiveTab(tabs: string[], activeInstanceId: string | null): void {
    const container = this.#allContainers().find((candidate) =>
      candidate.tabs.some((instanceId) => tabs.includes(instanceId)),
    );
    if (container && activeInstanceId && container.tabs.includes(activeInstanceId)) {
      container.activeInstanceId = activeInstanceId;
    }
  }

  #syncDrawerFromTopology(group: DockingTopology['groups'][number]): void {
    if (!group.edge) return;
    const drawer = this.#document.drawers[group.edge];
    drawer.mode = group.peeking || (group.autoHide && !group.collapsed)
      ? 'peek'
      : group.collapsed
        ? 'hidden'
        : 'pinned';
    const size = group.bounds
      ? group.edge === 'left' || group.edge === 'right'
        ? group.bounds.width
        : group.bounds.height
      : undefined;
    if (size && size > 0) {
      drawer.size = size;
      drawer.lastOpenSize = size;
    }
  }

  #emitLayout(operation: string): void {
    this.#events.emit('workbench.layout.changed@1', {
      workspaceId: this.#document.workspaceId,
      operation,
    });
  }
}

const DEFAULT_BOUNDS = { left: 80, top: 80, width: 640, height: 420 };

function normalizeAuthorization(
  value: boolean | LayoutMutationAuthorization,
): Required<LayoutMutationAuthorization> {
  return typeof value === 'boolean'
    ? { source: 'button', confirmed: value }
    : { source: value.source, confirmed: value.confirmed ?? false };
}

function topologyGroupKey(topology: DockingTopology, instanceId: string): string | null {
  const group = topology.groups.find((candidate) => candidate.tabs.includes(instanceId));
  return group ? `${group.location}:${group.groupId}` : null;
}

function requiresRelativeTarget(
  placement: EditorPlacement,
): placement is Extract<EditorPlacement, { mode: 'tab' | 'split' | 'replace' }> {
  return placement.mode === 'tab' || placement.mode === 'split' || placement.mode === 'replace';
}

function removeTab(container: { tabs: string[]; activeInstanceId: string | null }, instanceId: string): void {
  container.tabs = container.tabs.filter((id) => id !== instanceId);
  if (container.activeInstanceId === instanceId) container.activeInstanceId = container.tabs.at(-1) ?? null;
}

function clone<T>(value: T): T {
  return structuredClone(value);
}
