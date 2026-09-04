import type {
  EditorInstance,
  EditorPlacement,
  WorkspaceDocument,
  WorkspacePreset,
} from '../contracts.ts';
import { createDefaultDrawers } from '../fixtures/workspace-presets.ts';
import type { EditorRegistry } from './editor-registry.ts';

export type IdentifierFactory = (kind: 'instance' | 'area' | 'floating' | 'popout') => string;

export function createWorkspaceFromPreset(
  preset: WorkspacePreset,
  editors: EditorRegistry,
  createId: IdentifierFactory = randomIdentifier,
): WorkspaceDocument {
  const document: WorkspaceDocument = {
    schemaVersion: 3,
    workspaceId: preset.id,
    title: preset.title,
    customized: false,
    instances: {},
    areas: [],
    drawers: createDefaultDrawers(preset.drawerModes),
    floatingGroups: [],
    popoutGroups: [],
    activeAreaId: null,
    maximizedAreaId: null,
    dockviewLayout: { kind: 'preset', presetId: preset.id },
  };
  for (const contribution of preset.editors) {
    const definition = editors.get(contribution.editorId);
    const instance: EditorInstance = {
      instanceId: createId('instance'),
      editorId: definition.id,
      title: definition.title,
      localState: structuredClone(definition.initialState()),
      contextBinding: { mode: 'follow-global' },
      dirty: false,
      locked: contribution.locked ?? false,
      lifecycle: 'loading',
      executionMode: contribution.executionMode ?? 'planned',
      regions: [],
    };
    document.instances[instance.instanceId] = instance;
    placePresetInstance(document, instance, contribution.placement, createId);
  }
  return document;
}

function placePresetInstance(
  document: WorkspaceDocument,
  instance: EditorInstance,
  placement: EditorPlacement,
  createId: IdentifierFactory,
): void {
  if (placement.mode === 'drawer') {
    const drawer = document.drawers[placement.edge];
    drawer.tabs.push(instance.instanceId);
    drawer.activeInstanceId = instance.instanceId;
    return;
  }
  const current = document.areas.at(-1);
  if (placement.mode === 'tab' && current) {
    current.tabs.push(instance.instanceId);
    current.activeInstanceId = instance.instanceId;
    return;
  }
  const area = {
    areaId: createId('area'),
    tabs: [instance.instanceId],
    activeInstanceId: instance.instanceId,
    headerPosition: 'top' as const,
  };
  if (placement.mode === 'floating') {
    document.floatingGroups.push({
      groupId: createId('floating'),
      area,
      bounds: placement.bounds ?? { left: 80, top: 80, width: 640, height: 420 },
    });
    return;
  }
  if (placement.mode === 'popout') {
    document.popoutGroups.push({
      groupId: createId('popout'),
      area,
      bounds: placement.bounds ?? { left: 80, top: 80, width: 640, height: 420 },
      blocked: false,
    });
    return;
  }
  document.areas.push(area);
  document.activeAreaId = area.areaId;
}

export function randomIdentifier(kind: Parameters<IdentifierFactory>[0]): string {
  return `${kind}_${globalThis.crypto.randomUUID()}`;
}
