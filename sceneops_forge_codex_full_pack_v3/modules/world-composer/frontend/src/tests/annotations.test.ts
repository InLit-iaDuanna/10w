import assert from 'node:assert/strict';
import test from 'node:test';

import {
  SceneTransformResolver,
  loadSceneObjectIndex,
} from '@sceneops/scene-viewer';
import { HOME_SCENE_NODES } from '@sceneops/scene-viewer/fixtures';
import {
  restoreAnnotation,
  serializeAnnotation,
  validateAnnotation,
} from '../annotations.ts';
import type { AnnotationDetails, SurfacePinDetails, WorldAnnotation } from '../contracts.ts';
import {
  createObjectSpatialContext,
  createSceneSpatialContext,
  restoreSurfaceAnchor,
} from '../spatial-context.ts';
import { createVoiceDraftAnnotation } from '../voice-draft.ts';
import { annotation, clone, readJson } from './test-helpers.ts';

const details: AnnotationDetails[] = [
  { kind: 'object-pin' },
  {
    kind: 'surface-pin',
    geometryVersion: 'geometry-key-001',
    triangleVertexIndices: [12, 14, 15],
    barycentric: [0.2, 0.3, 0.5],
  },
  { kind: 'point', label: 'Sight line target' },
  {
    kind: 'region-volume',
    regionId: 'region_key_pickup',
    center: [2, 0.8, 3],
    size: [1, 1, 1],
    rotation: { x: 0, y: 0, z: 0, w: 1 },
  },
  {
    kind: 'path-trace',
    pathId: 'path_find_key',
    points: [
      { pointId: 'pathpoint_start', position: [0, 0, 4] },
      { pointId: 'pathpoint_key', position: [2, 0, 3] },
    ],
  },
  {
    kind: 'relation-link',
    relation: 'unlocks',
    sourceSceneopsId: 'sobj_key_instance',
    targetSceneopsId: 'sobj_home_door',
  },
  { kind: 'state', stateName: 'inventory.hasKey', expectedValue: true },
  {
    kind: 'sketch',
    strokes: [{ strokeId: 'stroke_visibility', points: [[1, 1, 1], [2, 1, 1]], color: '#eca85b', widthMeters: 0.02 }],
  },
  {
    kind: 'voice-draft',
    transcript: '把钥匙移到玩家更容易看见的位置。',
    locale: 'zh-CN',
    transcriptionConfidence: 1,
    audioEvidenceId: 'evidence_voice_mock',
    draft: true,
  },
];

test('round-trips all nine explicitly specified annotation capabilities', () => {
  for (const annotationDetails of details) {
    const original = annotation(annotationDetails);
    const restored = restoreAnnotation(serializeAnnotation(original));
    assert.deepEqual(restored, original);
    assert.notStrictEqual(restored, original);
  }
});

test('validates the public object-pin contract example', () => {
  const example = readJson<WorldAnnotation>('contracts/examples/object-pin.mock.json');
  validateAnnotation(example);
  assert.equal(example.context.mode, 'mock');
});

test('represents a free world point without inventing an object identity', () => {
  const spatial = createSceneSpatialContext('scene_remember_home_hall', [4, 1, 2], [0, 1, 0]);
  const record = annotation({ kind: 'point', label: 'Free point' }, spatial);
  validateAnnotation(record);
  assert.equal(record.context.spatial.reference.kind, 'scene');
});

test('rejects invalid surface anchors and keeps voice annotations in draft', () => {
  const badSurface = annotation({
    kind: 'surface-pin',
    geometryVersion: 'geometry-key-001',
    triangleVertexIndices: [0, 1, 2],
    barycentric: [0.2, 0.2, 0.2],
  });
  assert.throws(() => validateAnnotation(badSurface), /sum to one/);

  const voice = annotation({
    kind: 'voice-draft',
    transcript: '草稿',
    locale: 'zh-CN',
    transcriptionConfidence: 1,
    draft: true,
  });
  voice.status = 'open';
  assert.throws(() => validateAnnotation(voice), /remain drafts/);
});

test('uses inverse-transpose normals and marks topology changes stale', () => {
  const index = loadSceneObjectIndex(HOME_SCENE_NODES);
  const resolver = new SceneTransformResolver(index);
  const spatial = createObjectSpatialContext(
    index,
    resolver,
    'sobj_scaled_marker',
    [1, 0, 0],
    [1, 1, 0],
  );
  assert.notDeepEqual(spatial.worldNormal, spatial.localNormal);

  const surface: SurfacePinDetails = {
    kind: 'surface-pin',
    geometryVersion: 'geometry-marker-001',
    triangleVertexIndices: [0, 1, 2],
    barycentric: [0.2, 0.3, 0.5],
  };
  const restored = restoreSurfaceAnchor(spatial, surface, 'geometry-marker-001', resolver);
  assert.equal(restored.status, 'restored');
  const stale = restoreSurfaceAnchor(spatial, surface, 'geometry-marker-002', resolver);
  assert.equal(stale.status, 'stale');
  assert.match(stale.reason ?? '', /fallback is forbidden/);
});

test('rejects non-finite sketch data and object-only annotation without object reference', () => {
  const invalidSketch = annotation({
    kind: 'sketch',
    strokes: [{ strokeId: 'stroke_invalid', points: [[0, 0, 0], [Number.NaN, 1, 1]], color: '#fff', widthMeters: 0.1 }],
  });
  assert.throws(() => validateAnnotation(invalidSketch), /finite/);

  const invalidObjectPin = clone(annotation({ kind: 'object-pin' }));
  invalidObjectPin.context.spatial = createSceneSpatialContext('scene_remember_home_hall', [0, 0, 0], [0, 1, 0]);
  assert.throws(() => validateAnnotation(invalidObjectPin), /requires an object/);
});

test('voice input creates only a draft and reports unavailable transcription as blocked', () => {
  const base = annotation({
    kind: 'voice-draft',
    transcript: '占位',
    locale: 'zh-CN',
    transcriptionConfidence: 1,
    draft: true,
  });
  const { mode: _mode, ...context } = base.context;
  const created = createVoiceDraftAnnotation('ann_voice_created', context, {
    state: 'ready',
    transcript: '把钥匙标记为更明显。',
    locale: 'zh-CN',
    confidence: 0.98,
    audioEvidenceId: 'evidence_voice_mock',
    mode: 'mock',
  });
  assert.equal(created.state, 'created');
  if (created.state === 'created') assert.equal(created.annotation.status, 'draft');

  const blocked = createVoiceDraftAnnotation('ann_voice_blocked', context, {
    state: 'blocked',
    reason: 'Voice transcription adapter is not connected.',
  });
  assert.deepEqual(blocked, {
    state: 'blocked',
    mode: 'blocked',
    reason: 'Voice transcription adapter is not connected.',
  });
});
