import assert from 'node:assert/strict';
import test from 'node:test';

import {
  CameraComparisonSynchronizer,
  CameraStateError,
  SceneTransformResolver,
  SpatialMathError,
  captureCameraState,
  createMatrix4,
  invertMatrix4,
  loadSceneObjectIndex,
  multiplyMatrix4,
  restoreCameraState,
  type CameraPose,
  type CameraStatePort,
  type Vector3,
} from '../src/index.ts';
import {
  HOME_ISSUE_CAMERA,
  HOME_SCENE_ID,
  HOME_SCENE_NODES,
  HOME_SCENE_VERSION,
} from '../fixtures/index.ts';

test('converts points through hierarchy using column-major local and world matrices', () => {
  const transforms = new SceneTransformResolver(loadSceneObjectIndex(HOME_SCENE_NODES));
  assertVectorClose(
    transforms.localPointToWorld('sobj_key_instance', [0.5, 0.2, -1]),
    [2.5, 1, 2],
  );
  assertVectorClose(
    transforms.worldPointToLocal('sobj_key_instance', [2.5, 1, 2]),
    [0.5, 0.2, -1],
  );
});

test('uses inverse-transpose normal conversion for rotation with nonuniform scale', () => {
  const transforms = new SceneTransformResolver(loadSceneObjectIndex(HOME_SCENE_NODES));
  assertVectorClose(
    transforms.localPointToWorld('sobj_scaled_marker', [1, 2, 0]),
    [4, 2, 0],
  );
  const worldNormal = transforms.localNormalToWorld('sobj_scaled_marker', [1, 1, 0]);
  assertVectorClose(worldNormal, [-2 / Math.sqrt(13), 3 / Math.sqrt(13), 0]);
  assertVectorClose(
    transforms.worldNormalToLocal('sobj_scaled_marker', worldNormal),
    [1 / Math.sqrt(2), 1 / Math.sqrt(2), 0],
  );
});

test('inverts a general matrix and rejects a singular transform', () => {
  const matrix = createMatrix4([
    0, 2, 0, 0,
    -3, 0, 0, 0,
    0, 0, 4, 0,
    10, 5, -2, 1,
  ]);
  const product = multiplyMatrix4(matrix, invertMatrix4(matrix));
  assert.deepEqual(product.map(roundNearZero), [
    1, 0, 0, 0,
    0, 1, 0, 0,
    0, 0, 1, 0,
    0, 0, 0, 1,
  ]);

  assert.throws(
    () => invertMatrix4(createMatrix4([
      1, 0, 0, 0,
      0, 0, 0, 0,
      0, 0, 1, 0,
      0, 0, 0, 1,
    ])),
    (error) => error instanceof SpatialMathError && error.code === 'SINGULAR_MATRIX',
  );
});

test('captures and restores a camera only for the matching scene version', () => {
  const source = cameraPort(HOME_ISSUE_CAMERA);
  const capture = captureCameraState(source.port, {
    captureId: 'camera-capture-001',
    sceneId: HOME_SCENE_ID,
    sceneVersion: HOME_SCENE_VERSION,
    capturedAt: '2026-09-04T12:00:00Z',
    selectedSceneopsIds: ['sobj_home_door'],
  });
  const target = cameraPort(shiftedCamera());
  restoreCameraState(capture, target.port, {
    sceneId: HOME_SCENE_ID,
    sceneVersion: HOME_SCENE_VERSION,
  });
  assert.deepEqual(target.current(), HOME_ISSUE_CAMERA);

  assert.throws(
    () => restoreCameraState(capture, target.port, {
      sceneId: HOME_SCENE_ID,
      sceneVersion: 'scene-version-older',
    }),
    (error) => error instanceof CameraStateError && error.code === 'SCENE_VERSION_MISMATCH',
  );
});

test('synchronizes registered comparison cameras and reports an unknown source', () => {
  const left = cameraPort(HOME_ISSUE_CAMERA);
  const right = cameraPort(shiftedCamera());
  const comparison = new CameraComparisonSynchronizer();
  comparison.register('before', left.port);
  comparison.register('after', right.port);

  assert.deepEqual(comparison.synchronizeFrom('before'), ['after']);
  assert.deepEqual(right.current(), HOME_ISSUE_CAMERA);
  assert.throws(
    () => comparison.synchronizeFrom('missing'),
    (error) => error instanceof CameraStateError && error.code === 'UNKNOWN_VIEWPORT',
  );
});

test('rejects camera poses whose up vector is parallel to the view direction', () => {
  const invalid: CameraPose = {
    ...HOME_ISSUE_CAMERA,
    up: [4, 2, 4],
  };
  assert.throws(
    () => captureCameraState(cameraPort(invalid).port, {
      captureId: 'invalid-camera',
      sceneId: HOME_SCENE_ID,
      sceneVersion: HOME_SCENE_VERSION,
      capturedAt: '2026-09-04T12:00:00Z',
      selectedSceneopsIds: [],
    }),
    (error) => error instanceof CameraStateError && error.code === 'INVALID_CAMERA_POSE',
  );
});

function cameraPort(initial: CameraPose): {
  readonly port: CameraStatePort;
  readonly current: () => CameraPose;
} {
  let current = initial;
  return {
    port: {
      readCameraPose: () => current,
      applyCameraPose: (pose) => {
        current = pose;
      },
    },
    current: () => current,
  };
}

function shiftedCamera(): CameraPose {
  return {
    ...HOME_ISSUE_CAMERA,
    position: [20, 10, 5],
    target: [0, 1, 0],
  };
}

function assertVectorClose(actual: Vector3, expected: Vector3): void {
  for (let index = 0; index < 3; index += 1) {
    assert.ok(Math.abs(actual[index]! - expected[index]!) < 1e-10);
  }
}

function roundNearZero(value: number): number {
  if (Math.abs(value) < 1e-10) return 0;
  if (Math.abs(value - 1) < 1e-10) return 1;
  return value;
}
