import type {
  ContextBinding,
  DrawerMode,
  Edge,
  EditorDefinition,
  EditorInstance,
  JsonValue,
  WorkspaceDocument,
} from '../contracts.ts';

export const CURRENT_LAYOUT_SCHEMA_VERSION = 3;

export interface LayoutStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface LayoutEditorRegistry {
  get(editorId: string): EditorDefinition;
}

export type LayoutLoadResult =
  | { status: 'restored'; document: WorkspaceDocument }
  | { status: 'migrated'; fromVersion: 1 | 2; document: WorkspaceDocument }
  | { status: 'missing'; document: WorkspaceDocument }
  | {
      status: 'recovered';
      reason: 'CORRUPT_JSON' | 'UNSUPPORTED_SCHEMA' | 'INVALID_LAYOUT';
      document: WorkspaceDocument;
    };

export class LayoutRepository {
  readonly #storage: LayoutStorage;
  readonly #editors: LayoutEditorRegistry | undefined;

  constructor(storage: LayoutStorage, editors?: LayoutEditorRegistry) {
    this.#storage = storage;
    this.#editors = editors;
  }

  load(key: string, fallback: () => WorkspaceDocument): LayoutLoadResult {
    const serialized = this.#storage.getItem(key);
    if (serialized === null) return { status: 'missing', document: fallback() };
    let parsed: unknown;
    try {
      parsed = JSON.parse(serialized);
    } catch {
      return { status: 'recovered', reason: 'CORRUPT_JSON', document: fallback() };
    }
    const version = schemaVersion(parsed);
    if (version === null || version > CURRENT_LAYOUT_SCHEMA_VERSION || version < 1) {
      return { status: 'recovered', reason: 'UNSUPPORTED_SCHEMA', document: fallback() };
    }
    try {
      const migrated = migrateLayout(parsed);
      const document = this.#editors ? hydrateEditorState(migrated, this.#editors) : migrated;
      validateWorkspaceDocument(document);
      return version === CURRENT_LAYOUT_SCHEMA_VERSION
        ? { status: 'restored', document }
        : { status: 'migrated', fromVersion: version as 1 | 2, document };
    } catch {
      return { status: 'recovered', reason: 'INVALID_LAYOUT', document: fallback() };
    }
  }

  save(key: string, document: WorkspaceDocument): void {
    validateWorkspaceDocument(document);
    if (this.#editors) validateRegisteredEditors(document, this.#editors);
    this.#storage.setItem(key, exportLayout(document));
  }

  reset(key: string, fallback: () => WorkspaceDocument): WorkspaceDocument {
    this.#storage.removeItem(key);
    return fallback();
  }
}

export class DebouncedLayoutWriter {
  readonly #repository: LayoutRepository;
  readonly #delayMilliseconds: number;
  #timer: ReturnType<typeof setTimeout> | null = null;
  #pending: { key: string; document: WorkspaceDocument } | null = null;

  constructor(repository: LayoutRepository, delayMilliseconds = 180) {
    this.#repository = repository;
    this.#delayMilliseconds = delayMilliseconds;
  }

  schedule(key: string, document: WorkspaceDocument): void {
    this.#pending = { key, document: structuredClone(document) };
    if (this.#timer) clearTimeout(this.#timer);
    this.#timer = setTimeout(() => this.flush(), this.#delayMilliseconds);
  }

  flush(): void {
    if (!this.#pending) return;
    this.#repository.save(this.#pending.key, this.#pending.document);
    this.#pending = null;
    if (this.#timer) clearTimeout(this.#timer);
    this.#timer = null;
  }

  cancel(): void {
    if (this.#timer) clearTimeout(this.#timer);
    this.#timer = null;
    this.#pending = null;
  }
}

export function exportLayout(document: WorkspaceDocument): string {
  validateWorkspaceDocument(document);
  return `${JSON.stringify(document, null, 2)}\n`;
}

export function importLayout(serialized: string, editors?: LayoutEditorRegistry): WorkspaceDocument {
  const parsed: unknown = JSON.parse(serialized);
  const migrated = migrateLayout(parsed);
  const document = editors ? hydrateEditorState(migrated, editors) : migrated;
  validateWorkspaceDocument(document);
  return document;
}

export function migrateLayout(value: unknown): WorkspaceDocument {
  const version = schemaVersion(value);
  if (version === 3) return structuredClone(value) as WorkspaceDocument;
  if (version === 2) return migrateVersion2(value as Record<string, unknown>);
  if (version === 1) return migrateVersion1(value as Record<string, unknown>);
  throw new Error('Unsupported layout schema');
}

export function validateWorkspaceDocument(value: unknown): asserts value is WorkspaceDocument {
  if (!isRecord(value) || value.schemaVersion !== 3) throw new Error('Layout schema must be version 3');
  if (!nonEmptyString(value.workspaceId) || !nonEmptyString(value.title)) {
    throw new Error('Workspace identity is required');
  }
  if (typeof value.customized !== 'boolean' || !isRecord(value.instances)) {
    throw new Error('Invalid workspace metadata');
  }
  if (!isJsonValue(value.dockviewLayout)) throw new Error('Dockview layout must be JSON');

  const instances = value.instances as Record<string, unknown>;
  for (const [instanceId, instance] of Object.entries(instances)) {
    validateEditorInstance(instanceId, instance);
  }
  if (!Array.isArray(value.areas) || !isRecord(value.drawers) ||
      !Array.isArray(value.floatingGroups) || !Array.isArray(value.popoutGroups)) {
    throw new Error('Invalid workspace containers');
  }

  const document = value as unknown as WorkspaceDocument;
  const located = new Set<string>();
  const accept = (instanceId: string) => {
    if (!document.instances[instanceId]) throw new Error(`Container references unknown editor: ${instanceId}`);
    if (located.has(instanceId)) throw new Error(`Editor appears in multiple containers: ${instanceId}`);
    located.add(instanceId);
  };
  const containerIds = new Set<string>();
  for (const area of document.areas) {
    validateArea(area, true);
    acceptUniqueId(area.areaId, containerIds, 'area');
    for (const instanceId of area.tabs) accept(instanceId);
  }
  for (const edge of EDGES) {
    const drawer = document.drawers[edge];
    if (!drawer || drawer.edge !== edge || !DRAWER_MODES.includes(drawer.mode) ||
        !positiveFinite(drawer.size) || !positiveFinite(drawer.lastOpenSize)) {
      throw new Error('Invalid drawer');
    }
    validateTabs(drawer.tabs, drawer.activeInstanceId, false);
    for (const instanceId of drawer.tabs) accept(instanceId);
  }
  for (const group of document.floatingGroups) {
    validateFloatingGroup(group, false);
    acceptUniqueId(group.groupId, containerIds, 'floating group');
    acceptUniqueId(group.area.areaId, containerIds, 'floating area');
    for (const instanceId of group.area.tabs) accept(instanceId);
  }
  for (const group of document.popoutGroups) {
    validateFloatingGroup(group, true);
    acceptUniqueId(group.groupId, containerIds, 'popout group');
    acceptUniqueId(group.area.areaId, containerIds, 'popout area');
    for (const instanceId of group.area.tabs) accept(instanceId);
  }
  if (located.size !== Object.keys(document.instances).length) throw new Error('Unplaced editor instance');
  if (document.activeAreaId !== null && !document.areas.some((area) => area.areaId === document.activeAreaId)) {
    throw new Error('Invalid active area');
  }
  const allAreaIds = new Set([
    ...document.areas.map((area) => area.areaId),
    ...document.floatingGroups.map((group) => group.area.areaId),
    ...document.popoutGroups.map((group) => group.area.areaId),
  ]);
  if (document.maximizedAreaId !== null && !allAreaIds.has(document.maximizedAreaId)) {
    throw new Error('Invalid maximized area');
  }
  if (document.workspaceId === 'home' && !document.customized) {
    const homeInstances = Object.values(document.instances);
    const conversationId = homeInstances[0]?.instanceId;
    const validHomeArea = document.areas.length === 1 &&
      document.areas[0]?.tabs.length === 1 &&
      document.areas[0]?.tabs[0] === conversationId;
    const hidden = EDGES.every((edge) =>
      document.drawers[edge].mode === 'hidden' && document.drawers[edge].tabs.length === 0,
    );
    if (homeInstances.length !== 1 || homeInstances[0]?.editorId !== 'assistant.conversation' ||
        !validHomeArea || !hidden || document.floatingGroups.length > 0 || document.popoutGroups.length > 0) {
      throw new Error('Home must remain conversation-only');
    }
  }
}

function migrateVersion1(value: Record<string, unknown>): WorkspaceDocument {
  const workspaceId = stringValue(value.workspace_id, 'home');
  const legacyAreas = Array.isArray(value.areas) ? value.areas : [];
  const instances: Record<string, EditorInstance> = {};
  const areas = legacyAreas.map((entry, index) => {
    if (!isRecord(entry) || typeof entry.editor_id !== 'string') throw new Error('Invalid version 1 area');
    const instanceId = `migrated_instance_${index + 1}`;
    instances[instanceId] = createMigratedInstance(instanceId, entry.editor_id, entry.locked === true);
    return {
      areaId: `migrated_area_${index + 1}`,
      tabs: [instanceId],
      activeInstanceId: instanceId,
      headerPosition: 'top' as const,
    };
  });
  const legacyDrawers = isRecord(value.drawers) ? value.drawers : {};
  const drawers: WorkspaceDocument['drawers'] = {
    left: migratedDrawer('left', drawerMode(legacyDrawers.left)),
    right: migratedDrawer('right', drawerMode(legacyDrawers.right)),
    top: migratedDrawer('top', drawerMode(legacyDrawers.top)),
    bottom: migratedDrawer('bottom', drawerMode(legacyDrawers.bottom)),
  };
  return {
    schemaVersion: 3,
    workspaceId,
    title: workspaceId === 'home' ? '主页' : workspaceId,
    customized: workspaceId === 'home' &&
      !(Object.keys(instances).length === 1 && Object.values(instances)[0]?.editorId === 'assistant.conversation'),
    instances,
    areas,
    drawers,
    floatingGroups: [],
    popoutGroups: [],
    activeAreaId: areas[0]?.areaId ?? null,
    maximizedAreaId: null,
    dockviewLayout: { kind: 'preset', presetId: workspaceId, migratedFrom: 1 },
  };
}

function migrateVersion2(value: Record<string, unknown>): WorkspaceDocument {
  const migrated = structuredClone(value) as Record<string, unknown>;
  migrated.schemaVersion = 3;
  migrated.floatingGroups ??= [];
  migrated.popoutGroups ??= [];
  migrated.maximizedAreaId ??= null;
  migrated.customized ??= false;
  migrated.dockviewLayout ??= {
    kind: 'preset',
    presetId: stringValue(migrated.workspaceId ?? migrated.workspace_id, 'home'),
    migratedFrom: 2,
  };
  for (const instance of Object.values((migrated.instances ?? {}) as Record<string, Record<string, unknown>>)) {
    instance.executionMode ??= 'planned';
    instance.lifecycle ??= 'loading';
    instance.contextBinding ??= { mode: 'follow-global' } satisfies ContextBinding;
    instance.regions ??= [];
  }
  const migratedInstances = Object.values(
    (migrated.instances ?? {}) as Record<string, Record<string, unknown>>,
  );
  if (migrated.workspaceId === 'home' &&
      !(migratedInstances.length === 1 && migratedInstances[0]?.editorId === 'assistant.conversation')) {
    migrated.customized = true;
  }
  return migrated as unknown as WorkspaceDocument;
}

function createMigratedInstance(instanceId: string, editorId: string, locked: boolean): EditorInstance {
  return {
    instanceId,
    editorId,
    title: editorId,
    localState: null,
    contextBinding: { mode: 'follow-global' },
    dirty: false,
    locked,
    lifecycle: 'loading',
    executionMode: 'planned',
    regions: [],
  };
}

function migratedDrawer(edge: Edge, mode: DrawerMode) {
  return { edge, mode, size: 280, lastOpenSize: 280, tabs: [], activeInstanceId: null };
}

function schemaVersion(value: unknown): number | null {
  return isRecord(value) && typeof value.schemaVersion === 'number'
    ? value.schemaVersion
    : isRecord(value) && typeof value.schema_version === 'number'
      ? value.schema_version
      : null;
}

function drawerMode(value: unknown): DrawerMode {
  return DRAWER_MODES.includes(value as DrawerMode) ? (value as DrawerMode) : 'hidden';
}

function stringValue(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.length > 0 ? value : fallback;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function validateEditorInstance(instanceId: string, value: unknown): asserts value is EditorInstance {
  if (!isRecord(value) || value.instanceId !== instanceId || !nonEmptyString(value.editorId) ||
      !nonEmptyString(value.title) || typeof value.dirty !== 'boolean' || typeof value.locked !== 'boolean' ||
      !EDITOR_LIFECYCLES.includes(value.lifecycle as EditorInstance['lifecycle']) ||
      !EXECUTION_MODES.includes(value.executionMode as EditorInstance['executionMode']) ||
      !isContextBinding(value.contextBinding) || !isJsonValue(value.localState) || !Array.isArray(value.regions)) {
    throw new Error(`Invalid editor instance: ${instanceId}`);
  }
  const regionIds = new Set<string>();
  for (const region of value.regions) {
    if (!isRecord(region) || !nonEmptyString(region.regionId) || regionIds.has(region.regionId) ||
        !EDGES.includes(region.edge as Edge) || typeof region.visible !== 'boolean' ||
        !positiveFinite(region.size) || !isJsonValue(region.localState)) {
      throw new Error(`Invalid editor region: ${instanceId}`);
    }
    regionIds.add(region.regionId);
  }
}

function validateArea(value: unknown, requireTabs: boolean): asserts value is WorkspaceDocument['areas'][number] {
  if (!isRecord(value) || !nonEmptyString(value.areaId) ||
      !HEADER_POSITIONS.includes(value.headerPosition as WorkspaceDocument['areas'][number]['headerPosition']) ||
      !Array.isArray(value.tabs)) {
    throw new Error('Invalid area');
  }
  validateTabs(value.tabs, value.activeInstanceId, requireTabs);
}

function validateTabs(tabs: unknown[], activeInstanceId: unknown, requireTabs: boolean): asserts tabs is string[] {
  if ((requireTabs && tabs.length === 0) || tabs.some((id) => !nonEmptyString(id)) ||
      new Set(tabs).size !== tabs.length ||
      (activeInstanceId !== null && (!nonEmptyString(activeInstanceId) || !tabs.includes(activeInstanceId)))) {
    throw new Error('Invalid tabs');
  }
}

function validateFloatingGroup(value: unknown, popout: boolean): void {
  if (!isRecord(value) || !nonEmptyString(value.groupId) || !isBounds(value.bounds)) {
    throw new Error('Invalid floating group');
  }
  validateArea(value.area, true);
  if (popout && typeof value.blocked !== 'boolean') throw new Error('Invalid popout group');
}

function isBounds(value: unknown): boolean {
  return isRecord(value) && finite(value.left) && finite(value.top) &&
    positiveFinite(value.width) && positiveFinite(value.height);
}

function isContextBinding(value: unknown): value is ContextBinding {
  if (!isRecord(value)) return false;
  if (value.mode === 'follow-global') return Object.keys(value).length === 1;
  return value.mode === 'pinned' && isRecord(value.context) && isJsonValue(value.context);
}

function isJsonValue(value: unknown): value is JsonValue {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (Array.isArray(value)) return value.every(isJsonValue);
  return isRecord(value) && Object.values(value).every(isJsonValue);
}

function hydrateEditorState(document: WorkspaceDocument, editors: LayoutEditorRegistry): WorkspaceDocument {
  const hydrated = structuredClone(document);
  for (const instance of Object.values(hydrated.instances)) {
    const definition = editors.get(instance.editorId);
    instance.localState = definition.restoreState(instance.localState);
  }
  validateRegisteredEditors(hydrated, editors);
  return hydrated;
}

function validateRegisteredEditors(document: WorkspaceDocument, editors: LayoutEditorRegistry): void {
  for (const instance of Object.values(document.instances)) editors.get(instance.editorId);
}

function acceptUniqueId(value: string, ids: Set<string>, label: string): void {
  if (ids.has(value)) throw new Error(`Duplicate ${label} ID: ${value}`);
  ids.add(value);
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0;
}

function finite(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function positiveFinite(value: unknown): value is number {
  return finite(value) && value > 0;
}

const EDGES: Edge[] = ['left', 'right', 'top', 'bottom'];
const DRAWER_MODES: DrawerMode[] = ['hidden', 'peek', 'pinned'];
const HEADER_POSITIONS: WorkspaceDocument['areas'][number]['headerPosition'][] = ['top', 'bottom', 'left', 'right'];
const EDITOR_LIFECYCLES: EditorInstance['lifecycle'][] = [
  'loading', 'empty', 'ready', 'offline', 'permission-denied', 'failed', 'disconnected',
];
const EXECUTION_MODES: EditorInstance['executionMode'][] = ['live', 'cached', 'mock', 'planned', 'blocked'];
