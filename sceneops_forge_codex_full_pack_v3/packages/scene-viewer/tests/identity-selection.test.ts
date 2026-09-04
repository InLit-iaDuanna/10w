import assert from 'node:assert/strict';
import test from 'node:test';

import {
  SceneIdentityError,
  SceneSelectionModel,
  loadSceneObjectIndex,
  type SceneNodeDescriptor,
} from '../src/index.ts';
import { HOME_SCENE_NODES } from '../fixtures/index.ts';

test('loads stable IDs and preserves identity across rename while copies receive new identity', () => {
  const index = loadSceneObjectIndex(HOME_SCENE_NODES);
  assert.equal(index.size, 4);
  assert.equal(index.sceneopsIdForNode('node-home-door'), 'sobj_home_door');

  const renamed = index.rename('sobj_home_door', 'Front Entrance');
  assert.equal(renamed.sceneopsId, 'sobj_home_door');
  assert.equal(index.sceneopsIdForNode('node-home-door'), 'sobj_home_door');

  const source = index.require('sobj_key_instance');
  const copied = index.copy({
    sourceSceneopsId: source.sceneopsId,
    newSceneopsId: 'sobj_key_instance_copy_01',
    newNodeKey: 'node-key-instance-copy-01',
    name: 'Spare Front Door Key',
  });
  assert.equal(copied.copiedFromSceneopsId, source.sceneopsId);
  assert.equal(copied.assetId, source.assetId);
  assert.notEqual(copied.sceneopsId, source.sceneopsId);
  assert.notStrictEqual(copied.localMatrix, source.localMatrix);
  assert.deepEqual(copied.localMatrix, source.localMatrix);
});

test('rejects absent, duplicate, reused, and cyclic stable identities', () => {
  assert.throws(
    () => loadSceneObjectIndex([{
      nodeKey: 'node-without-id',
      name: 'Missing ID',
      extras: {},
    }]),
    (error) => error instanceof SceneIdentityError && error.code === 'MISSING_SCENEOPS_ID',
  );

  const duplicateNodes: readonly SceneNodeDescriptor[] = [
    { nodeKey: 'a', name: 'A', extras: { sceneops_id: 'sobj_same' } },
    { nodeKey: 'b', name: 'B', extras: { sceneops_id: 'sobj_same' } },
  ];
  assert.throws(
    () => loadSceneObjectIndex(duplicateNodes),
    (error) => error instanceof SceneIdentityError && error.code === 'DUPLICATE_SCENEOPS_ID',
  );

  const cyclicNodes: readonly SceneNodeDescriptor[] = [
    { nodeKey: 'a', name: 'A', extras: { sceneops_id: 'sobj_a' }, parentNodeKey: 'b' },
    { nodeKey: 'b', name: 'B', extras: { sceneops_id: 'sobj_b' }, parentNodeKey: 'a' },
  ];
  assert.throws(
    () => loadSceneObjectIndex(cyclicNodes),
    (error) => error instanceof SceneIdentityError && error.code === 'CYCLIC_HIERARCHY',
  );

  const index = loadSceneObjectIndex(HOME_SCENE_NODES);
  assert.throws(
    () => index.copy({
      sourceSceneopsId: 'sobj_key_instance',
      newSceneopsId: 'sobj_key_instance',
      newNodeKey: 'new-node',
    }),
    (error) => error instanceof SceneIdentityError && error.code === 'IDENTITY_REUSE',
  );
});

test('selection follows global context, remains stable while pinned, and restores snapshots', () => {
  const index = loadSceneObjectIndex(HOME_SCENE_NODES);
  const selection = new SceneSelectionModel(index);

  selection.setGlobalSelection(['sobj_home_door', 'sobj_key_instance']);
  assert.equal(selection.active.primarySceneopsId, 'sobj_key_instance');
  selection.pin();
  selection.setGlobalSelection(['sobj_scaled_marker']);
  assert.deepEqual(selection.active.selectedSceneopsIds, ['sobj_home_door', 'sobj_key_instance']);

  selection.toggle('sobj_home_door');
  assert.deepEqual(selection.active.selectedSceneopsIds, ['sobj_key_instance']);
  const snapshot = selection.snapshot();

  selection.followGlobal();
  assert.deepEqual(selection.active.selectedSceneopsIds, ['sobj_scaled_marker']);
  selection.restore(snapshot);
  assert.equal(selection.bindingMode, 'pinned');
  assert.deepEqual(selection.active.selectedSceneopsIds, ['sobj_key_instance']);
});

test('selection rejects objects absent from the stable scene index', () => {
  const selection = new SceneSelectionModel(loadSceneObjectIndex(HOME_SCENE_NODES));
  assert.throws(
    () => selection.setGlobalSelection(['sobj_not_in_scene']),
    (error) => error instanceof SceneIdentityError && error.code === 'UNKNOWN_SCENE_OBJECT',
  );
});
