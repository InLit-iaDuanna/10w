import {
  resolveContext,
  type AreaHeaderContract,
  type EditorRegistry,
  type JsonValue,
  type VisibilityCoordinator,
  type WorkbenchCommandBus,
  type WorkbenchContext,
  type WorkbenchEventBus,
  type WorkspaceCoordinator,
} from '@sceneops/forge-shell';
import type { ForgeShellRuntime } from './ForgeShell';

export function createForgeShellRuntime(options: {
  coordinator: WorkspaceCoordinator;
  editors: EditorRegistry;
  visibility: VisibilityCoordinator;
  commands: WorkbenchCommandBus;
  events: WorkbenchEventBus;
  getGlobalContext(): WorkbenchContext;
  onAreaAction(instanceId: string, action: AreaHeaderContract['actions'][number]): void;
}): ForgeShellRuntime {
  const { coordinator } = options;
  return {
    editors: options.editors,
    visibility: options.visibility,
    commands: options.commands,
    events: options.events,
    getInstance: (instanceId) => coordinator.getInstance(instanceId),
    getDrawer: (edge) => coordinator.getDrawer(edge),
    syncDrawer: (drawer) => coordinator.syncDrawer(drawer),
    editorAvailability: (editorId) => coordinator.editorAvailability(editorId),
    updateVisibility: (instanceId, visible) => {
      const instance = coordinator.getInstance(instanceId);
      if (!instance) return;
      options.visibility.update(instanceId, options.editors.get(instance.editorId), visible);
    },
    resolveContext: (instanceId) => {
      const instance = coordinator.getInstance(instanceId);
      if (!instance) throw new Error(`Unknown editor instance: ${instanceId}`);
      return resolveContext(options.getGlobalContext(), instance.contextBinding);
    },
    loadEditor: (instanceId) => coordinator.loadEditor(instanceId),
    updateLocalState: (instanceId, patch) => {
      const current = coordinator.getInstance(instanceId)?.localState;
      if (current === undefined) throw new Error(`Unknown editor instance: ${instanceId}`);
      coordinator.updateLocalState(instanceId, mergeJsonPatch(current, patch));
    },
    close: (instanceId, confirmed = false) => coordinator.closeEditor(instanceId, {
      source: 'button',
      confirmed,
    }),
    setTitle: (instanceId, title) => coordinator.setTitle(instanceId, title),
    beginDockviewMutation: (kind) => coordinator.beginDockviewMutation(kind),
    completeDockviewMutation: (kind, topology) => coordinator.completeDockviewMutation(kind, topology),
    syncDockviewLayout: (layout, topology) => coordinator.syncDockviewLayout(layout, topology),
    onAreaAction: options.onAreaAction,
  };
}

function mergeJsonPatch(current: JsonValue, patch: Partial<JsonValue>): JsonValue {
  if (isJsonObject(current) && isJsonObject(patch)) return { ...current, ...patch };
  return structuredClone(patch as JsonValue);
}

function isJsonObject(value: unknown): value is Record<string, JsonValue> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
