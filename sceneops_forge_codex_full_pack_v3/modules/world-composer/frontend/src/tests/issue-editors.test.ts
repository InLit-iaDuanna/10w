import assert from 'node:assert/strict';
import test from 'node:test';

import { HOME_ISSUE_CAMERA } from '@sceneops/scene-viewer/fixtures';
import { buildWorldEditorScreen } from '../editor-state.ts';
import { worldEditorDefinitions } from '../editors/definitions.ts';
import {
  createFixedCameraCaptureRequest,
  restoreIssueContext,
  type IssueRestorationPorts,
  type WorldIssueContext,
} from '../issue-restoration.ts';
import { pinWorldContext, resolveWorldContext } from '../state/context.ts';
import { createWorldOverlayRegistry } from '../world-overlays.ts';
import { clone, readWorld } from './test-helpers.ts';

function issue(): WorldIssueContext {
  return {
    issueId: 'issue_key_visibility_001',
    projectId: 'prj_find_my_way_home',
    sceneId: 'scn_home_hall',
    sceneVersion: 'scnver_home_hall_001',
    targetSceneopsIds: ['sobj_home_key', 'sobj_home_entrance'],
    camera: HOME_ISSUE_CAMERA,
    pathId: 'path_find_key_and_home',
    evidenceIds: ['evidence_key_before'],
    gameStateVersion: 'game-state-v1',
    gameState: { quest: 'find_key', hasKey: false },
    buildId: 'build_home_a',
    playtestRunId: 'playtest_home_a',
    playtestStepId: 'step_home_a_042',
    mode: 'mock',
  };
}

function createPorts(existingEvidence = new Set(['evidence_key_before'])): {
  ports: IssueRestorationPorts;
  calls: {
    cameras: unknown[];
    selections: string[][];
    paths: string[];
    contexts: unknown[];
  };
} {
  const calls = { cameras: [] as unknown[], selections: [] as string[][], paths: [] as string[], contexts: [] as unknown[] };
  return {
    calls,
    ports: {
      restoreCamera(camera) { calls.cameras.push(structuredClone(camera)); },
      selectObjects(ids) { calls.selections.push([...ids]); },
      showPath(pathId) { calls.paths.push(pathId); },
      hasEvidence(evidenceId) { return existingEvidence.has(evidenceId); },
      updateGlobalContext(context) { calls.contexts.push(structuredClone(context)); },
    },
  };
}

test('restores exact scene, renamed objects, camera, path, evidence, and follow context', () => {
  const scene = readWorld('fixtures/remember-home/world.mock.json');
  scene.objects.find((object) => object.sceneopsId === 'sobj_home_key')!.displayName = 'RenamedKey';
  const { ports, calls } = createPorts();
  const first = restoreIssueContext(scene, issue(), { mode: 'follow-global' }, ports);
  const second = restoreIssueContext(scene, issue(), { mode: 'follow-global' }, ports);

  assert.equal(first.state, 'restored');
  assert.equal(first.mode, 'mock');
  assert.deepEqual(calls.selections[0], ['sobj_home_key', 'sobj_home_entrance']);
  assert.deepEqual(calls.cameras[0], HOME_ISSUE_CAMERA);
  assert.deepEqual(calls.cameras[1], calls.cameras[0]);
  assert.deepEqual(second, first);
  assert.deepEqual(calls.paths, ['path_find_key_and_home', 'path_find_key_and_home']);
  assert.equal(calls.contexts.length, 2);
});

test('blocks exact-version mismatch and preserves pinned context', () => {
  const scene = readWorld('fixtures/remember-home/world.mock.json');
  const staleIssue = issue();
  staleIssue.sceneVersion = 'scnver_home_hall_old';
  const stalePorts = createPorts();
  const blocked = restoreIssueContext(scene, staleIssue, { mode: 'follow-global' }, stalePorts.ports);
  assert.equal(blocked.state, 'blocked');
  assert.equal(blocked.mode, 'blocked');
  assert.equal(stalePorts.calls.cameras.length, 0);

  const pinnedPorts = createPorts();
  const pinned = restoreIssueContext(
    scene,
    issue(),
    { mode: 'pinned', context: { selectedSceneObjectIds: ['sobj_player_spawn'] } },
    pinnedPorts.ports,
  );
  assert.equal(pinned.state, 'restored');
  assert.equal(pinnedPorts.calls.contexts.length, 0);
});

test('reports partial object and evidence restoration without guessing by name', () => {
  const scene = readWorld('fixtures/remember-home/world.mock.json');
  const partialIssue = issue();
  partialIssue.targetSceneopsIds.push('sobj_deleted_key_copy');
  const { ports, calls } = createPorts(new Set());
  const result = restoreIssueContext(scene, partialIssue, { mode: 'follow-global' }, ports);
  assert.equal(result.state, 'partial');
  assert.deepEqual(calls.selections[0], ['sobj_home_key', 'sobj_home_entrance']);
  assert.equal(result.components.find((entry) => entry.component === 'objects')?.status, 'missing');
  assert.equal(result.components.find((entry) => entry.component === 'evidence')?.status, 'missing');
});

test('creates only a planned fixed-camera capture request', () => {
  const request = createFixedCameraCaptureRequest({
    requestId: 'capture_request_home_001',
    sceneId: 'scn_home_hall',
    sceneVersion: 'scnver_home_hall_001',
    camera: HOME_ISSUE_CAMERA,
    widthPixels: 1920,
    heightPixels: 1080,
    overlayIds: ['scene.object-ids', 'scene.navmesh'],
  });
  assert.equal(request.mode, 'planned');
  assert.throws(
    () => createFixedCameraCaptureRequest({ ...request, widthPixels: 0 }),
    /positive/,
  );
});

test('all eight lazy editor definitions expose every required visible state', async () => {
  assert.equal(worldEditorDefinitions.length, 8);
  assert.equal(new Set(worldEditorDefinitions.map((definition) => definition.id)).size, 8);
  for (const definition of worldEditorDefinitions) {
    const loaded = await definition.load();
    assert.equal(typeof loaded.default, 'function');
    for (const status of [
      'loading',
      'empty',
      'ready',
      'failed',
      'disconnected',
      'permission-denied',
      'module-disabled',
      'stale',
    ]) {
      assert.ok(definition.visibleStates.includes(status), `${definition.id} lacks ${status}`);
      const screen = buildWorldEditorScreen(definition.id, definition.title, {
        status: status as Parameters<typeof buildWorldEditorScreen>[2]['status'],
        mode: status === 'module-disabled' ? 'blocked' : 'mock',
        sceneId: 'scn_home_hall',
        sceneVersion: 'scnver_home_hall_001',
      });
      assert.ok(screen.statusLabel.length > 0);
      assert.ok(screen.modeLabel.length > 0);
    }
  }
});

test('viewport serialization excludes runtime resources and hidden views report suspension', async () => {
  const viewport = worldEditorDefinitions.find((definition) => definition.id === 'scene.viewport.3d');
  assert.ok(viewport?.serializeState && viewport.restoreState);
  const serializable = {
    camera: HOME_ISSUE_CAMERA,
    overlayIds: ['scene.object-ids'],
    widthPixels: 800,
    heightPixels: 600,
    visible: false,
    active: true,
    runtimeResource: { dispose() {} },
  };
  const saved = viewport.serializeState(serializable as never) as Record<string, unknown>;
  assert.equal('runtimeResource' in saved, false);
  const loaded = await viewport.load();
  const render = loaded.default as (
    input: Parameters<typeof buildWorldEditorScreen>[2],
    state: Omit<typeof serializable, 'runtimeResource'>,
  ) => ReturnType<typeof buildWorldEditorScreen>;
  const screen = render(
    { status: 'ready', mode: 'mock', sceneId: 'scn_home_hall', sceneVersion: 'scnver_home_hall_001' },
    saved as never,
  );
  assert.equal(screen.status, 'suspended');
});

test('follow and pinned world context resolve independently', () => {
  const globalContext = {
    projectId: 'prj_home',
    sceneId: 'scn_home_hall',
    selectedSceneObjectIds: ['sobj_home_key'],
    activeIssueId: null,
  };
  assert.deepEqual(resolveWorldContext({ mode: 'follow-global' }, globalContext), globalContext);
  const binding = pinWorldContext({ ...clone(globalContext), selectedSceneObjectIds: ['sobj_home_entrance'] });
  globalContext.selectedSceneObjectIds = ['sobj_player_spawn'];
  assert.deepEqual(resolveWorldContext(binding, globalContext).selectedSceneObjectIds, ['sobj_home_entrance']);
});

test('world overlay registry exposes all required overlays with truthful availability', () => {
  const scene = readWorld('fixtures/remember-home/world.mock.json');
  const registry = createWorldOverlayRegistry();
  const context = { scene, renderBuffers: {}, heatmapArtifactId: null };
  assert.deepEqual(registry.list(context).map((entry) => entry.id), [
    'scene.object-ids',
    'scene.colliders',
    'scene.navmesh',
    'scene.paths',
    'scene.depth',
    'scene.normals',
    'scene.masks',
    'scene.heatmaps',
  ]);
  assert.equal(registry.resolve('scene.navmesh', context).payload.mode, 'mock');
  assert.throws(() => registry.resolve('scene.depth', context), /unavailable/);
  const depth = registry.resolve('scene.depth', {
    ...context,
    renderBuffers: { depth: 'buffer_depth_mock_001' },
  });
  assert.deepEqual(depth.payload.data, { bufferId: 'buffer_depth_mock_001' });
});
