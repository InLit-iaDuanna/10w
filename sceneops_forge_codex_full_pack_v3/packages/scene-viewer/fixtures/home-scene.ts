import {
  createMatrix4,
  type PerspectiveCameraPose,
  type SceneNodeDescriptor,
} from '../src/index.ts';

export const HOME_SCENE_ID = 'scene_remember_home_hall';
export const HOME_SCENE_VERSION = 'scene-version-0007';

export const HOME_SCENE_NODES: readonly SceneNodeDescriptor[] = Object.freeze([
  Object.freeze({
    nodeKey: 'node-hall-root',
    name: 'Home Hall',
    extras: Object.freeze({ sceneops_id: 'sobj_home_hall' }),
    localMatrix: createMatrix4([
      1, 0, 0, 0,
      0, 1, 0, 0,
      0, 0, 1, 0,
      0, 0, 0, 1,
    ]),
  }),
  Object.freeze({
    nodeKey: 'node-home-door',
    name: 'Home Entrance',
    extras: Object.freeze({ sceneops_id: 'sobj_home_door' }),
    parentNodeKey: 'node-hall-root',
    assetId: 'asset_home_door',
    localMatrix: createMatrix4([
      1, 0, 0, 0,
      0, 1, 0, 0,
      0, 0, 1, 0,
      4, 0, 8, 1,
    ]),
  }),
  Object.freeze({
    nodeKey: 'node-key-instance',
    name: 'Front Door Key',
    extras: Object.freeze({ sceneops_id: 'sobj_key_instance' }),
    parentNodeKey: 'node-hall-root',
    assetId: 'asset_brass_key',
    localMatrix: createMatrix4([
      1, 0, 0, 0,
      0, 1, 0, 0,
      0, 0, 1, 0,
      2, 0.8, 3, 1,
    ]),
  }),
  Object.freeze({
    nodeKey: 'node-scaled-marker',
    name: 'Nonuniform Scale Marker',
    extras: Object.freeze({ sceneops_id: 'sobj_scaled_marker' }),
    parentNodeKey: 'node-hall-root',
    localMatrix: createMatrix4([
      0, 2, 0, 0,
      -3, 0, 0, 0,
      0, 0, 4, 0,
      10, 0, 0, 1,
    ]),
  }),
]);

export const HOME_ISSUE_CAMERA: PerspectiveCameraPose = Object.freeze({
  projection: 'perspective',
  position: Object.freeze([8, 3, 12] as const),
  target: Object.freeze([4, 1, 8] as const),
  up: Object.freeze([0, 1, 0] as const),
  verticalFovRadians: Math.PI / 3,
  nearClipMeters: 0.1,
  farClipMeters: 500,
  coordinateSpace: 'world',
  axisConvention: 'right-handed-y-up',
  units: 'meters',
});
