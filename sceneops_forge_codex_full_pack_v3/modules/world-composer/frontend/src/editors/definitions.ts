import type { JsonValue } from '../contracts.ts';
import {
  restoreViewportState,
  serializeViewportState,
  type SceneViewportState,
} from './SceneViewportEditor.ts';

export interface WorldEditorDefinition {
  id: string;
  title: string;
  icon: string;
  category: 'scene';
  load: () => Promise<{ default: (...args: never[]) => unknown }>;
  defaultPlacement: 'center' | 'left' | 'right' | 'bottom';
  minWidth: number;
  minHeight: number;
  singleton: boolean;
  requiredPermissions: string[];
  optionalIntegrations: string[];
  contextBinding: true;
  visibleStates: string[];
  serializeState?: (state: unknown) => JsonValue;
  restoreState?: (value: JsonValue) => unknown;
}

const visibleStates = [
  'loading',
  'empty',
  'ready',
  'failed',
  'disconnected',
  'permission-denied',
  'module-disabled',
  'stale',
] as const;

const viewportDefinition: WorldEditorDefinition = {
  id: 'scene.viewport.3d',
  title: '3D 视口',
  icon: 'cube',
  category: 'scene',
  load: () => import('./SceneViewportEditor.ts'),
  defaultPlacement: 'center',
  minWidth: 640,
  minHeight: 400,
  singleton: false,
  requiredPermissions: ['scene:read'],
  optionalIntegrations: ['blender', 'unity'],
  contextBinding: true,
  visibleStates: [...visibleStates, 'suspended'],
  serializeState: (state) => serializeViewportState(state as SceneViewportState) as unknown as JsonValue,
  restoreState: (value) => restoreViewportState(value),
};

function editor(
  id: string,
  title: string,
  icon: string,
  placement: WorldEditorDefinition['defaultPlacement'],
  load: WorldEditorDefinition['load'],
  permission = 'scene:read',
): WorldEditorDefinition {
  return {
    id,
    title,
    icon,
    category: 'scene',
    load,
    defaultPlacement: placement,
    minWidth: 280,
    minHeight: 220,
    singleton: false,
    requiredPermissions: [permission],
    optionalIntegrations: ['blender', 'unity'],
    contextBinding: true,
    visibleStates: [...visibleStates],
  };
}

export const worldEditorDefinitions: WorldEditorDefinition[] = [
  viewportDefinition,
  editor('scene.outliner', '场景大纲', 'hierarchy', 'left', () => import('./SceneOutlinerEditor.ts')),
  editor(
    'scene.object.inspector',
    '对象检查器',
    'inspect',
    'right',
    () => import('./ObjectInspectorEditor.ts'),
  ),
  editor(
    'scene.annotations',
    '空间标注',
    'pin',
    'bottom',
    () => import('./AnnotationListEditor.ts'),
    'scene:annotate',
  ),
  editor('scene.world.graph', '世界图', 'graph', 'bottom', () => import('./WorldGraphEditor.ts')),
  editor(
    'scene.path-region',
    '路径与区域',
    'path',
    'bottom',
    () => import('./PathRegionEditor.ts'),
    'scene:write',
  ),
  editor('scene.navmesh', '导航网格', 'navigation', 'bottom', () => import('./NavMeshEditor.ts')),
  editor(
    'scene.lighting',
    '灯光目标',
    'light',
    'right',
    () => import('./LightingEditor.ts'),
    'scene:write',
  ),
];
