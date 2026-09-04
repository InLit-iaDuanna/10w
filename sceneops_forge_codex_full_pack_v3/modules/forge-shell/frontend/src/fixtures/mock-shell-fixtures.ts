import type {
  DockingEnginePort,
  DockingTopology,
  EditorDefinition,
  EditorInstance,
  EditorPlacement,
  JsonValue,
} from '../contracts.ts';
import { BUILT_IN_WORKSPACE_PRESETS } from './workspace-presets.ts';

export const MOCK_EXECUTION_MODE = 'mock' as const;

export function createMockEditor(editorId: string, options: {
  singleton?: boolean;
  heavy?: boolean;
  renderCapable?: boolean;
  requiredPermissions?: string[];
  requiredIntegrations?: string[];
  rejectLoad?: boolean;
} = {}): EditorDefinition {
  return {
    id: editorId,
    title: editorId,
    icon: 'fixture',
    category: 'fixture',
    load: options.rejectLoad
      ? async () => { throw new Error(`Mock load failed: ${editorId}`); }
      : async () => ({ default: { fixture: editorId } }),
    defaultPlacement: { mode: 'tab' },
    ...(options.singleton === undefined ? {} : { singleton: options.singleton }),
    ...(options.heavy === undefined ? {} : { heavy: options.heavy }),
    renderPolicy: options.renderCapable ? 'suspend-when-hidden' : 'always',
    ...(options.requiredPermissions === undefined ? {} : { requiredPermissions: options.requiredPermissions }),
    ...(options.requiredIntegrations === undefined ? {} : { requiredIntegrations: options.requiredIntegrations }),
    initialState: () => ({ fixture: editorId }),
    serializeState: (state) => structuredClone(state),
    restoreState: (value) => structuredClone(value),
  };
}

export function createPresetMockEditors(): EditorDefinition[] {
  const ids = new Set(BUILT_IN_WORKSPACE_PRESETS.flatMap((preset) => preset.editors.map((item) => item.editorId)));
  return [...ids].map((id) => createMockEditor(id, {
    renderCapable: id.includes('viewport') || id.includes('game-view') || id.includes('preview.3d'),
  }));
}

export class RecordingDockingPort implements DockingEnginePort {
  readonly calls: Array<{ operation: string; detail: unknown }> = [];
  layout: JsonValue = { fixture: 'mock-dockview-layout' };
  popoutBlocked = false;
  topology: DockingTopology = { groups: [], activeInstanceId: null, maximizedInstanceId: null };

  capture(): JsonValue {
    return structuredClone(this.layout);
  }

  describe(): DockingTopology {
    return structuredClone(this.topology);
  }

  restore(layout: JsonValue): void {
    this.layout = structuredClone(layout);
    this.calls.push({ operation: 'restore', detail: structuredClone(layout) });
  }

  open(instance: EditorInstance, placement: EditorPlacement): boolean {
    this.calls.push({ operation: 'open', detail: { instanceId: instance.instanceId, placement } });
    return placement.mode === 'popout' ? !this.popoutBlocked : true;
  }

  close(instanceId: string): void {
    this.calls.push({ operation: 'close', detail: { instanceId } });
  }

  move(instance: EditorInstance, placement: EditorPlacement): boolean {
    this.calls.push({ operation: 'move', detail: { instanceId: instance.instanceId, placement } });
    return placement.mode === 'popout' ? !this.popoutBlocked : true;
  }

  switchEditor(instance: EditorInstance): void {
    this.calls.push({ operation: 'switch', detail: { instanceId: instance.instanceId, editorId: instance.editorId } });
  }

  join(sourceInstanceId: string, targetInstanceId: string): void {
    this.calls.push({ operation: 'join', detail: { sourceInstanceId, targetInstanceId } });
  }

  maximize(instanceId: string | null): void {
    this.calls.push({ operation: 'maximize', detail: { instanceId } });
  }

  focus(instanceId: string): void {
    this.calls.push({ operation: 'focus', detail: { instanceId } });
  }
}

export function deterministicIdentifierFactory() {
  let sequence = 0;
  return (kind: 'instance' | 'area' | 'floating' | 'popout') => `${kind}_fixture_${++sequence}`;
}
