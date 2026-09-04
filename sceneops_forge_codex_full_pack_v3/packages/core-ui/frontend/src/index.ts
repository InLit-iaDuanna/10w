export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export type ExecutionMode = 'live' | 'cached' | 'mock' | 'planned' | 'blocked';
export type Edge = 'left' | 'right' | 'top' | 'bottom';
export type DrawerMode = 'hidden' | 'peek' | 'pinned';
export type SplitDirection = 'left' | 'right' | 'above' | 'below';
export type EditorLifecycle =
  | 'loading'
  | 'empty'
  | 'ready'
  | 'offline'
  | 'permission-denied'
  | 'failed'
  | 'disconnected';

export interface CameraPose {
  position: readonly [number, number, number];
  target: readonly [number, number, number];
  up: readonly [number, number, number];
  coordinateSpace: string;
  axisConvention: string;
}

export interface WorkbenchContext {
  projectId: string | null;
  branchId: string | null;
  sceneId: string | null;
  selectedSceneObjectIds: string[];
  selectedAssetIds: string[];
  activeFeatureId: string | null;
  activeTaskId: string | null;
  activeChangeSetId: string | null;
  activeRenderJobId: string | null;
  activeBuildId: string | null;
  activePlaytestRunId: string | null;
  activeIssueId: string | null;
  cameraPose?: CameraPose;
  timelineTime?: number;
}

export type ContextBinding =
  | { mode: 'follow-global' }
  | { mode: 'pinned'; context: Partial<WorkbenchContext> };

export type EditorPlacement =
  | { mode: 'replace'; relativeToInstanceId?: string }
  | { mode: 'tab'; relativeToInstanceId?: string }
  | { mode: 'split'; direction: SplitDirection; relativeToInstanceId?: string }
  | { mode: 'floating'; bounds?: FloatingBounds }
  | { mode: 'popout'; bounds?: FloatingBounds }
  | { mode: 'drawer'; edge: Edge };

export interface FloatingBounds {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface EditorHostProps<TState = JsonValue> {
  instanceId: string;
  context: WorkbenchContext;
  contextBinding: ContextBinding;
  localState: TState;
  commands: WorkbenchCommandClient;
  events: WorkbenchEventClient;
  updateLocalState(patch: Partial<TState>): void;
  close(): void;
  setTitle(title: string): void;
  suspended: boolean;
}

export interface WorkbenchCommandClient {
  availability(commandId: string, context: CommandExecutionContext, input: unknown): CommandAvailability;
  execute<TResult>(commandId: string, context: CommandExecutionContext, input: unknown): Promise<TResult>;
}

export interface WorkbenchEventClient {
  on<TKey extends ShellEventName>(
    eventName: TKey,
    listener: (payload: ShellEventMap[TKey]) => void,
  ): () => void;
}

export interface LazyEditorModule {
  default: unknown;
}

export interface EditorDefinition<TState = JsonValue> {
  id: string;
  title: string;
  icon: string;
  category: string;
  load(): Promise<LazyEditorModule>;
  defaultPlacement: EditorPlacement;
  minWidth?: number;
  minHeight?: number;
  singleton?: boolean;
  heavy?: boolean;
  renderPolicy?: 'always' | 'suspend-when-hidden';
  requiredPermissions?: string[];
  requiredIntegrations?: string[];
  optionalIntegrations?: string[];
  initialState(): TState;
  serializeState(state: TState): JsonValue;
  restoreState(value: JsonValue): TState;
}

export interface EditorAvailability {
  status: 'available' | 'permission-denied' | 'offline';
  missingPermissions: string[];
  missingIntegrations: string[];
  message: string | null;
  suggestedActions: string[];
}

export interface EditorInstance {
  instanceId: string;
  editorId: string;
  title: string;
  localState: JsonValue;
  contextBinding: ContextBinding;
  dirty: boolean;
  locked: boolean;
  lifecycle: EditorLifecycle;
  executionMode: ExecutionMode;
  regions: EditorRegionState[];
}

export interface EditorRegionState {
  regionId: string;
  edge: Edge;
  visible: boolean;
  size: number;
  localState: JsonValue;
}

export interface AreaState {
  areaId: string;
  tabs: string[];
  activeInstanceId: string | null;
  headerPosition: 'top' | 'bottom' | 'left' | 'right';
}

export interface DrawerState {
  edge: Edge;
  mode: DrawerMode;
  size: number;
  lastOpenSize: number;
  tabs: string[];
  activeInstanceId: string | null;
}

export interface FloatingGroupState {
  groupId: string;
  area: AreaState;
  bounds: FloatingBounds;
}

export interface PopoutGroupState extends FloatingGroupState {
  blocked: boolean;
}

export interface WorkspaceDocument {
  schemaVersion: 3;
  workspaceId: string;
  title: string;
  customized: boolean;
  instances: Record<string, EditorInstance>;
  areas: AreaState[];
  drawers: Record<Edge, DrawerState>;
  floatingGroups: FloatingGroupState[];
  popoutGroups: PopoutGroupState[];
  activeAreaId: string | null;
  maximizedAreaId: string | null;
  dockviewLayout: JsonValue;
}

export interface WorkspacePreset {
  id: string;
  title: string;
  judgeMode?: boolean;
  editors: Array<{
    editorId: string;
    placement: EditorPlacement;
    locked?: boolean;
    executionMode?: ExecutionMode;
  }>;
  drawerModes?: Partial<Record<Edge, DrawerMode>>;
}

export type DockingLocation = 'grid' | 'floating' | 'popout' | 'edge';

export interface DockingGroupTopology {
  groupId: string;
  location: DockingLocation;
  edge?: Edge;
  tabs: string[];
  activeInstanceId: string | null;
  headerPosition: AreaState['headerPosition'];
  bounds?: FloatingBounds;
  collapsed?: boolean;
  peeking?: boolean;
  autoHide?: boolean;
}

/** A serializable projection of Dockview's live group graph and persisted bounds. */
export interface DockingTopology {
  groups: DockingGroupTopology[];
  activeInstanceId: string | null;
  maximizedInstanceId: string | null;
}

export type DockingMutationKind =
  | 'add'
  | 'remove'
  | 'move'
  | 'float'
  | 'popout'
  | 'maximize'
  | 'tab-group'
  | 'load'
  | 'clear';

export interface DockingEnginePort {
  capture(): JsonValue;
  describe(): DockingTopology;
  restore(layout: JsonValue): void | Promise<void>;
  open(instance: EditorInstance, placement: EditorPlacement): void | boolean | Promise<void | boolean>;
  close(instanceId: string): void | Promise<void>;
  move(instance: EditorInstance, placement: EditorPlacement): void | boolean | Promise<void | boolean>;
  switchEditor(instance: EditorInstance): void | Promise<void>;
  join(sourceInstanceId: string, targetInstanceId: string): void | Promise<void>;
  maximize(instanceId: string | null): void | Promise<void>;
  focus(instanceId: string): void | Promise<void>;
}

export type CommandSource = 'assistant' | 'button' | 'menu' | 'keyboard' | 'tool-library' | 'workflow';

export interface CommandAvailability {
  available: boolean;
  reason?: string;
}

export interface CommandExecutionContext {
  workbench: WorkbenchContext;
  permissions: ReadonlySet<string>;
  connectedIntegrations: ReadonlySet<string>;
  source: CommandSource;
}

export interface WorkbenchCommandDefinition<TInput, TResult> {
  id: string;
  title: string;
  requiredPermissions?: string[];
  requiredIntegrations?: string[];
  validate(input: unknown): input is TInput;
  canExecute(context: CommandExecutionContext, input: TInput): CommandAvailability;
  execute(context: CommandExecutionContext, input: TInput): Promise<TResult>;
}

export interface ShellEventMap {
  'workbench.editor.opened@1': { instance: EditorInstance; placement: EditorPlacement; source: CommandSource };
  'workbench.editor.closed@1': { instance: EditorInstance };
  'workbench.editor.load_failed@1': { instanceId: string; editorId: string; code: 'EDITOR_LOAD_FAILED'; message: string };
  'workbench.layout.changed@1': { workspaceId: string; operation: string };
  'workbench.visibility.changed@1': { instanceId: string; visible: boolean; suspended: boolean };
  'workbench.context.binding_changed@1': { instanceId: string; binding: ContextBinding };
  'workbench.drawer.changed@1': { edge: Edge; mode: DrawerMode; size: number };
}

export type ShellEventName = keyof ShellEventMap;

export interface AreaHeaderContract {
  height: 32;
  title: string;
  contextSummary: string;
  mode: ExecutionMode;
  binding: ContextBinding;
  active: boolean;
  compact: boolean;
  actions: Array<
    | 'editor-menu'
    | 'follow-pin'
    | 'add'
    | 'split'
    | 'float'
    | 'maximize-restore'
    | 'more'
    | 'close'
  >;
}
