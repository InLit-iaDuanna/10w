import type { DockviewApi, IDockviewPanel, SerializedDockview } from 'dockview-react';
import type {
  DockingEnginePort,
  DockingGroupTopology,
  DockingTopology,
  DrawerState,
  EditorInstance,
  EditorPlacement,
  FloatingBounds,
  JsonValue,
  WorkspaceDocument,
} from '@sceneops/forge-shell';

const PANEL_COMPONENT = 'forge-editor-host';
export type DockviewWorkspaceRestoreStatus = 'restored' | 'materialized' | 'recovered';

export class DockviewPort implements DockingEnginePort {
  readonly #api: DockviewApi;
  #regionSplits = false;

  constructor(api: DockviewApi) {
    this.#api = api;
  }

  capture(): JsonValue {
    // Dockview returns optional undefined fields; persist its JSON wire representation.
    return JSON.parse(JSON.stringify(this.#api.toJSON())) as JsonValue;
  }

  describe(): DockingTopology {
    const edgeSizes = this.#api.toJSON().edgeGroups;
    const groups = this.#api.groups.map((group): DockingGroupTopology => {
      const location = group.api.location;
      const bounds = location.type === 'popout'
        ? popoutWindowBounds(location.getWindow)
        : group.api.boundingBox;
      return {
        groupId: group.id,
        location: location.type,
        ...(location.type === 'edge' ? { edge: location.position } : {}),
        tabs: group.panels.map((panel) => panel.id),
        activeInstanceId: group.activePanel?.id ?? null,
        headerPosition: group.api.getHeaderPosition(),
        ...(bounds ? { bounds: { ...bounds } } : {}),
        ...(location.type === 'edge'
          ? {
              ...(edgeSizes?.[location.position]?.size === undefined ? {} : { expandedSize: edgeSizes[location.position]!.size }),
              collapsed: group.api.isCollapsed(),
              peeking: group.api.isPeeking(),
              autoHide: group.api.isAutoHide(),
            }
          : {}),
      };
    });
    const maximized = this.#api.groups.find((group) => group.api.isMaximized());
    return {
      groups,
      activeInstanceId: this.#api.activePanel?.id ?? null,
      maximizedInstanceId: maximized?.activePanel?.id ?? null,
    };
  }

  restore(layout: JsonValue): void {
    if (isPresetMarker(layout)) {
      this.#api.clear();
      for (const edge of EDGES) {
        if (this.#api.getEdgeGroup(edge)) this.#api.removeEdgeGroup(edge);
      }
      return;
    }
    const snapshot = structuredClone(layout) as unknown as SerializedDockview;
    // Edge constraints are shell policy, not saved user geometry. Older
    // snapshots carried the previous 180/640 limits.
    for (const edge of EDGES) {
      const group = snapshot.edgeGroups?.[edge];
      if (!group) continue;
      group.minimumSize = 12;
      delete group.maximumSize;
    }
    this.#api.fromJSON(snapshot, { reuseExistingPanels: true });
    if (this.#regionSplits) this.enableRegionSplits();
  }

  async restoreWorkspace(document: WorkspaceDocument): Promise<DockviewWorkspaceRestoreStatus> {
    if (!isPresetMarker(document.dockviewLayout)) {
      try {
        this.restore(document.dockviewLayout);
        await this.#api.popoutRestorationPromise;
        if (!topologyMatchesDocument(this.describe(), document)) {
          throw new Error('Dockview snapshot does not match workspace instances');
        }
        return 'restored';
      } catch {
        this.#api.clear();
        await this.#materializeWorkspace(document);
        return 'recovered';
      }
    }
    this.#api.clear();
    await this.#materializeWorkspace(document);
    return 'materialized';
  }

  async #materializeWorkspace(document: WorkspaceDocument): Promise<void> {
    let gridAnchor: string | undefined;
    for (const [areaIndex, area] of document.areas.entries()) {
      const first = area.tabs[0];
      if (!first) continue;
      await this.#openRequired(
        document.instances[first]!,
        areaIndex === 0 || !gridAnchor
          ? { mode: 'tab' }
          : { mode: 'split', direction: 'right', relativeToInstanceId: gridAnchor },
      );
      gridAnchor = first;
      for (const instanceId of area.tabs.slice(1)) {
        await this.#openRequired(document.instances[instanceId]!, {
          mode: 'tab', relativeToInstanceId: first,
        });
      }
      this.#api.getPanel(first)?.group.api.setHeaderPosition(area.headerPosition);
      if (area.activeInstanceId) this.#api.getPanel(area.activeInstanceId)?.api.setActive();
    }
    for (const edge of EDGES) {
      const drawer = document.drawers[edge];
      for (const instanceId of drawer.tabs) {
        await this.#openRequired(document.instances[instanceId]!, { mode: 'drawer', edge });
      }
      this.syncDrawer(drawer);
    }
    for (const group of document.floatingGroups) {
      const first = group.area.tabs[0];
      if (!first) continue;
      await this.#openRequired(document.instances[first]!, { mode: 'floating', bounds: group.bounds });
      for (const instanceId of group.area.tabs.slice(1)) {
        await this.#openRequired(document.instances[instanceId]!, { mode: 'tab', relativeToInstanceId: first });
      }
      if (group.area.activeInstanceId) this.#api.getPanel(group.area.activeInstanceId)?.api.setActive();
    }
    for (const group of document.popoutGroups) {
      const first = group.area.tabs[0];
      if (!first) continue;
      await this.#openRequired(document.instances[first]!, { mode: 'popout', bounds: group.bounds });
      for (const instanceId of group.area.tabs.slice(1)) {
        await this.#openRequired(document.instances[instanceId]!, { mode: 'tab', relativeToInstanceId: first });
      }
      if (group.area.activeInstanceId) this.#api.getPanel(group.area.activeInstanceId)?.api.setActive();
    }
    const maximized = document.maximizedAreaId
      ? this.#instanceForArea(document, document.maximizedAreaId)
      : null;
    if (maximized) this.maximize(maximized);
  }

  async open(instance: EditorInstance, placement: EditorPlacement, options?: { preserveFocus?: boolean }): Promise<boolean> {
    // Empty edge groups survive their last tab. A default insertion would reuse
    // that active (possibly collapsed) group, hiding the restored home screen.
    const emptyWorkspace = this.#api.groups.every(group => group.panels.length === 0);
    if (emptyWorkspace && placement.mode === 'tab') {
      for (const edge of EDGES) {
        if (this.#api.getEdgeGroup(edge)) this.#api.removeEdgeGroup(edge);
      }
    }
    const replacementId = placement.mode === 'replace'
      ? placement.relativeToInstanceId ?? this.#api.activePanel?.id
      : undefined;
    const panel = this.#api.addPanel({
      id: instance.instanceId,
      component: PANEL_COMPONENT,
      title: instance.title,
      params: { instanceId: instance.instanceId, editorId: instance.editorId },
      renderer: 'always',
      ...(options?.preserveFocus ? { inactive: true } : {}),
      ...(placement.mode === 'drawer'
        ? { position: { referenceGroup: this.#ensureEdgeGroup(placement.edge).id } }
        : placement.mode === 'tab' && emptyWorkspace
          ? { position: { direction: 'right' as const } }
          : addPanelPlacement(placement, this.#api.activePanel?.id)),
    });
    if (placement.mode === 'replace') closeReplacement(this.#api, panel, replacementId);
    applyInitialSplitSize(panel, placement);
    if (placement.mode !== 'popout') return true;
    const opened = await this.#api.addPopoutGroup(panel, popoutOptions(placement.bounds));
    if (!opened) panel.api.close();
    return opened;
  }

  close(instanceId: string): void {
    const panel = this.#api.getPanel(instanceId);
    const group = panel?.group;
    panel?.api.close();
    if (group?.api.location.type === 'edge' && group.panels.length === 0) {
      this.#api.removeEdgeGroup(group.api.location.position);
    }
  }

  async move(instance: EditorInstance, placement: EditorPlacement): Promise<boolean> {
    const panel = this.#api.getPanel(instance.instanceId);
    if (placement.mode === 'drawer') {
      if (!panel) return this.open(instance, placement);
      this.#moveToEdge(panel, placement.edge);
      return true;
    }
    if (!panel) return this.open(instance, placement);
    if (placement.mode === 'floating') {
      this.#api.addFloatingGroup(panel, floatingOptions(placement.bounds));
      return true;
    }
    if (placement.mode === 'popout') {
      return this.#api.addPopoutGroup(panel, popoutOptions(placement.bounds));
    }
    const reference = this.#referencePanel(placement.relativeToInstanceId, instance.instanceId);
    if (!reference) return true;
    if (placement.mode === 'split') {
      panel.api.moveTo({ group: reference.group, position: splitPosition(placement.direction) });
      applyInitialSplitSize(panel, placement);
    } else {
      panel.api.moveTo({ group: reference.group });
      if (placement.mode === 'replace') reference.api.close();
    }
    return true;
  }

  switchEditor(instance: EditorInstance): void {
    const panel = this.#requirePanel(instance.instanceId);
    panel.api.setTitle(instance.title);
    panel.api.updateParameters({ instanceId: instance.instanceId, editorId: instance.editorId });
  }

  join(sourceInstanceId: string, targetInstanceId: string): void {
    const source = this.#requirePanel(sourceInstanceId);
    const target = this.#requirePanel(targetInstanceId);
    source.group.api.moveTo({ group: target.group });
  }

  maximize(instanceId: string | null): void {
    if (instanceId === null) {
      this.#api.exitMaximizedGroup();
      return;
    }
    this.#requirePanel(instanceId).api.maximize();
  }

  focus(instanceId: string): void {
    this.#requirePanel(instanceId).api.setActive();
  }

  /**
   * Retire the legacy outer drawers in favour of ordinary Dockview grid
   * groups. Moving the existing groups keeps their panels and renderers alive;
   * no editor instance is created or discarded by this migration.
   */
  enableRegionSplits(): void {
    this.#regionSplits = true;
    let anchor = this.#api.groups.find((group) => group.api.location.type === 'grid');
    const rememberedEdgeSizes = this.#api.toJSON().edgeGroups;
    for (const group of this.#api.groups) {
      if (group.api.location.type === 'grid') setRegionConstraints(group);
    }

    for (const edge of EDGES) {
      const edgeApi = this.#api.getEdgeGroup(edge);
      if (!edgeApi) continue;
      const edgeGroup = this.#api.groups.find((group) => group.id === edgeApi.id);
      if (!edgeGroup) continue;
      if (edgeGroup.panels.length === 0) {
        this.#api.removeEdgeGroup(edge);
        continue;
      }
      const firstPanel = edgeGroup.panels[0]!;
      // Serialized edge size is the expanded memory even when the visible
      // group is collapsed to its label strip. Read both values before moveTo,
      // which is allowed to dispose the legacy edge view.
      const size = rememberedEdgeSizes?.[edge]?.size ??
        (edge === 'left' || edge === 'right' ? edgeApi.width : edgeApi.height);

      if (!anchor) {
        anchor = this.#api.addGroup({ direction: 'right' });
        // An empty root group is only a temporary native anchor. Moving the
        // first legacy group within it avoids inventing a placeholder panel.
        edgeGroup.api.moveTo({ group: anchor, position: 'center' });
      } else {
        edgeGroup.api.moveTo({ group: anchor, position: splitPositionForEdge(edge) });
      }
      const migrated = firstPanel.group;
      setRegionConstraints(migrated);
      if (Number.isFinite(size) && size > 0) {
        migrated.api.setSize(edge === 'left' || edge === 'right' ? { width: size } : { height: size });
      }
      this.#api.removeEdgeGroup(edge);
      anchor = anchor.api.location.type === 'grid' ? anchor : migrated;
    }
  }

  moveRegionToWorkspaceEdge(instanceId: string, edge: DrawerState['edge']): void {
    this.#requirePanel(instanceId).group.api.moveTo({ position: splitPositionForEdge(edge) });
  }

  regionElement(instanceId: string): HTMLElement {
    return this.#requirePanel(instanceId).group.element;
  }

  resizeRegion(instanceId: string, edge: DrawerState['edge'], size: number): void {
    const group = this.#requirePanel(instanceId).group;
    if (group.api.location.type !== 'grid') return;
    for (const candidate of this.#api.groups) {
      if (candidate.api.location.type === 'grid') setRegionConstraints(candidate);
    }
    const nextSize = Math.max(REGION_MINIMUM_SIZE, size);
    group.api.setSize(edge === 'left' || edge === 'right'
      ? { width: nextSize }
      : { height: nextSize });
  }

  collapsedRegionIds(): string[] {
    return this.#api.groups.flatMap((group) =>
      group.api.location.type === 'grid' &&
      (group.api.width <= REGION_MINIMUM_SIZE || group.api.height <= REGION_MINIMUM_SIZE)
        ? group.panels.map((panel) => panel.id)
        : [],
    );
  }

  /** Return the tabs in the grid region immediately across one panel edge. */
  adjacentRegionIds(instanceId: string, edge: DrawerState['edge'], crossRatio: number): string[] {
    const current = this.#api.getPanel(instanceId)?.group;
    if (!current || current.api.location.type !== 'grid') return [];
    const currentBounds = current.api.boundingBox;
    if (!currentBounds) return [];

    const horizontalEdge = edge === 'left' || edge === 'right';
    const ratio = Math.max(0, Math.min(1, crossRatio));
    const boundary = horizontalEdge
      ? currentBounds.left + (edge === 'right' ? currentBounds.width : 0)
      : currentBounds.top + (edge === 'bottom' ? currentBounds.height : 0);
    const crossCoordinate = horizontalEdge
      ? currentBounds.top + currentBounds.height * ratio
      : currentBounds.left + currentBounds.width * ratio;
    const candidates = this.#api.groups.flatMap((group) => {
      if (group.id === current.id || group.api.location.type !== 'grid') return [];
      const bounds = group.api.boundingBox;
      if (!bounds) return [];
      const candidateBoundary = horizontalEdge
        ? bounds.left + (edge === 'left' ? bounds.width : 0)
        : bounds.top + (edge === 'top' ? bounds.height : 0);
      const crossStart = horizontalEdge ? bounds.top : bounds.left;
      const crossSize = horizontalEdge ? bounds.height : bounds.width;
      if (Math.abs(candidateBoundary - boundary) > REGION_ADJACENCY_TOLERANCE ||
          crossCoordinate < crossStart - REGION_ADJACENCY_TOLERANCE ||
          crossCoordinate > crossStart + crossSize + REGION_ADJACENCY_TOLERANCE) return [];
      return [{ group, distance: Math.abs(crossCoordinate - (crossStart + crossSize / 2)) }];
    }).sort((a, b) => a.distance - b.distance);

    return candidates[0]?.group.panels.map((panel) => panel.id) ?? [];
  }

  syncDrawer(drawer: DrawerState): void {
    let edgeGroup = this.#api.getEdgeGroup(drawer.edge);
    if (!edgeGroup && (drawer.mode !== 'hidden' || drawer.tabs.length > 0)) {
      edgeGroup = this.#ensureEdgeGroup(drawer.edge, drawer.size);
    }
    for (const instanceId of drawer.tabs) {
      const panel = this.#api.getPanel(instanceId);
      if (!panel) continue;
      if (edgeGroup && panel.group.id !== edgeGroup.id) this.#moveToEdge(panel, drawer.edge);
    }
    if (!edgeGroup) return;
    const active = drawer.activeInstanceId ? this.#api.getPanel(drawer.activeInstanceId) : undefined;
    const savedSize = this.#api.toJSON().edgeGroups?.[drawer.edge]?.size;
    if (savedSize !== drawer.size && edgeGroup.isPeeking()) this.#api.peekEdgeGroup(drawer.edge, false);
    if (savedSize !== drawer.size) edgeGroup.setSize(
      drawer.edge === 'left' || drawer.edge === 'right'
        ? { width: drawer.size }
        : { height: drawer.size },
    );
    if (drawer.mode === 'pinned') {
      if (edgeGroup.isPeeking()) this.#api.peekEdgeGroup(drawer.edge, false);
      if (edgeGroup.isAutoHide()) edgeGroup.setAutoHide(false);
      if (edgeGroup.isCollapsed()) edgeGroup.expand();
      if (active && !active.api.isActive) active.api.setActive();
      return;
    }
    if (!edgeGroup.isAutoHide()) edgeGroup.setAutoHide(true);
    if (!edgeGroup.isCollapsed()) edgeGroup.collapse();
    if (drawer.mode === 'peek' && active && !active.api.isActive) active.api.setActive();
    if (edgeGroup.isPeeking() !== (drawer.mode === 'peek')) {
      this.#api.peekEdgeGroup(drawer.edge, drawer.mode === 'peek');
    }
  }

  #moveToEdge(panel: IDockviewPanel, edge: DrawerState['edge']): void {
    const edgeGroup = this.#ensureEdgeGroup(edge);
    if (panel.group.id !== edgeGroup.id) {
      panel.api.moveTo({ group: this.#api.groups.find((group) => group.id === edgeGroup.id)! });
    }
  }

  #ensureEdgeGroup(edge: DrawerState['edge'], size?: number) {
    return this.#api.getEdgeGroup(edge) ?? this.#api.addEdgeGroup(edge, {
      id: `forge-edge-${edge}`,
      ...(size === undefined ? {} : { initialSize: size }),
      minimumSize: 12,
      collapsedSize: 12,
      collapsed: true,
      autoHide: true,
    });
  }

  async #openRequired(instance: EditorInstance, placement: EditorPlacement): Promise<void> {
    const opened = await this.open(instance, placement);
    if (opened === false) throw new Error(`Dockview could not restore ${instance.instanceId}`);
  }

  #instanceForArea(document: WorkspaceDocument, areaId: string): string | null {
    const area = [
      ...document.areas,
      ...document.floatingGroups.map((group) => group.area),
      ...document.popoutGroups.map((group) => group.area),
    ].find((candidate) => candidate.areaId === areaId);
    return area?.activeInstanceId ?? area?.tabs[0] ?? null;
  }

  #referencePanel(referenceId: string | undefined, movingId: string): IDockviewPanel | undefined {
    if (referenceId && referenceId !== movingId) return this.#api.getPanel(referenceId);
    const active = this.#api.activePanel;
    return active?.id === movingId ? undefined : active;
  }

  #requirePanel(instanceId: string): IDockviewPanel {
    const panel = this.#api.getPanel(instanceId);
    if (!panel) throw new Error(`Dockview panel is not mounted: ${instanceId}`);
    return panel;
  }
}

function addPanelPlacement(placement: EditorPlacement, activePanelId?: string) {
  const referencePanel = 'relativeToInstanceId' in placement
    ? placement.relativeToInstanceId ?? activePanelId
    : activePanelId;
  if (placement.mode === 'floating') return { floating: floatingOptions(placement.bounds) };
  if (placement.mode === 'split') {
    return { position: { referencePanel, direction: placement.direction } };
  }
  if (placement.mode === 'tab' || placement.mode === 'replace' || placement.mode === 'popout') {
    return referencePanel ? { position: { referencePanel, direction: 'within' as const } } : {};
  }
  return {};
}

function splitPosition(direction: 'left' | 'right' | 'above' | 'below') {
  if (direction === 'above') return 'top' as const;
  if (direction === 'below') return 'bottom' as const;
  return direction;
}

function applyInitialSplitSize(panel: IDockviewPanel, placement: EditorPlacement): void {
  if (placement.mode !== 'split' || placement.initialSize === undefined) return;
  panel.group.api.setSize(placement.direction === 'left' || placement.direction === 'right'
    ? { width: placement.initialSize }
    : { height: placement.initialSize });
}

function floatingOptions(bounds?: FloatingBounds) {
  const value = bounds ?? { left: 80, top: 80, width: 640, height: 420 };
  return { position: { left: value.left, top: value.top }, width: value.width, height: value.height };
}

function popoutOptions(bounds?: FloatingBounds) {
  return {
    popoutUrl: '/popout.html',
    position: bounds ?? { left: 80, top: 80, width: 640, height: 420 },
  };
}

function popoutWindowBounds(getWindow: () => Window): FloatingBounds | undefined {
  try {
    const window = getWindow();
    return {
      left: window.screenX,
      top: window.screenY,
      width: window.outerWidth,
      height: window.outerHeight,
    };
  } catch {
    return undefined;
  }
}

function closeReplacement(api: DockviewApi, panel: IDockviewPanel, explicitReference?: string): void {
  const referenceId = explicitReference;
  if (!referenceId || referenceId === panel.id) return;
  api.getPanel(referenceId)?.api.close();
}

function isPresetMarker(value: JsonValue): boolean {
  return typeof value === 'object' && value !== null && !Array.isArray(value) && value.kind === 'preset';
}

function topologyMatchesDocument(topology: DockingTopology, document: WorkspaceDocument): boolean {
  const topologyIds = topology.groups.flatMap((group) => group.tabs);
  const documentIds = Object.keys(document.instances);
  if (topologyIds.length !== documentIds.length ||
      new Set(topologyIds).size !== topologyIds.length ||
      topologyIds.some((instanceId) => !document.instances[instanceId])) {
    return false;
  }
  const topologyContainers = topology.groups
    .filter((group) => group.tabs.length > 0)
    .map((group) => normalizedContainer(
      group.location === 'edge' ? `edge:${group.edge ?? 'invalid'}` : group.location,
      group.tabs,
    ))
    .sort();
  const documentContainers = [
    ...document.areas
      .filter((area) => area.tabs.length > 0)
      .map((area) => normalizedContainer('grid', area.tabs)),
    ...EDGES.flatMap((edge) => {
      const drawer = document.drawers[edge];
      return drawer.tabs.length > 0 ? [normalizedContainer(`edge:${edge}`, drawer.tabs)] : [];
    }),
    ...document.floatingGroups
      .filter((group) => group.area.tabs.length > 0)
      .map((group) => normalizedContainer('floating', group.area.tabs)),
    ...document.popoutGroups
      .filter((group) => group.area.tabs.length > 0)
      .map((group) => normalizedContainer('popout', group.area.tabs)),
  ].sort();
  return topologyContainers.length === documentContainers.length &&
    topologyContainers.every((container, index) => container === documentContainers[index]);
}

function normalizedContainer(location: string, tabs: string[]): string {
  return JSON.stringify([location, [...tabs].sort()]);
}

const EDGES: DrawerState['edge'][] = ['left', 'right', 'top', 'bottom'];
const REGION_MINIMUM_SIZE = 12;
const REGION_ADJACENCY_TOLERANCE = 4;

function setRegionConstraints(group: IDockviewPanel['group']): void {
  group.api.setConstraints({
    minimumWidth: REGION_MINIMUM_SIZE,
    minimumHeight: REGION_MINIMUM_SIZE,
  });
}

function splitPositionForEdge(edge: DrawerState['edge']) {
  if (edge === 'top') return 'top' as const;
  if (edge === 'bottom') return 'bottom' as const;
  return edge;
}
