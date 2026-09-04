import { canonicalCoordinateSystem, type CameraPose } from '../contracts.ts';
import {
  buildWorldEditorScreen,
  type WorldEditorInput,
  type WorldEditorScreen,
} from '../editor-state.ts';

export interface SceneViewportState {
  camera: CameraPose | null;
  overlayIds: string[];
  widthPixels: number;
  heightPixels: number;
  visible: boolean;
  active: boolean;
}

export default function SceneViewportEditor(
  input: WorldEditorInput,
  state: SceneViewportState,
): WorldEditorScreen {
  const status = !state.visible || !state.active ? 'suspended' : input.status;
  return buildWorldEditorScreen('scene.viewport.3d', '3D 视口', { ...input, status }, [
    { id: 'editor-role', label: '编辑器', value: '主空间编辑器' },
    {
      id: 'coordinates',
      label: '坐标',
      value: `${canonicalCoordinateSystem.handedness}-handed · ${canonicalCoordinateSystem.upAxis}-up · ${canonicalCoordinateSystem.units}`,
    },
    { id: 'viewport-size', label: '尺寸', value: `${state.widthPixels}×${state.heightPixels}` },
    { id: 'overlays', label: '叠加层', value: [...state.overlayIds] },
  ]);
}

export function serializeViewportState(state: SceneViewportState): SceneViewportState {
  if (!Number.isInteger(state.widthPixels) || !Number.isInteger(state.heightPixels)) {
    throw new Error('Viewport dimensions must be integers');
  }
  if (state.widthPixels < 0 || state.heightPixels < 0) {
    throw new Error('Viewport dimensions must not be negative');
  }
  return {
    camera: state.camera === null ? null : structuredClone(state.camera),
    overlayIds: [...state.overlayIds],
    widthPixels: state.widthPixels,
    heightPixels: state.heightPixels,
    visible: state.visible,
    active: state.active,
  };
}

export function restoreViewportState(value: unknown): SceneViewportState {
  if (typeof value !== 'object' || value === null) throw new Error('Invalid viewport state');
  const state = value as SceneViewportState;
  if (!Array.isArray(state.overlayIds)) throw new Error('Invalid viewport overlays');
  if (typeof state.visible !== 'boolean' || typeof state.active !== 'boolean') {
    throw new Error('Invalid viewport visibility');
  }
  return serializeViewportState(state);
}
