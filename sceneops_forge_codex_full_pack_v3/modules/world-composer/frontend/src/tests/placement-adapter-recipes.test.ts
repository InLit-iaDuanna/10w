import assert from 'node:assert/strict';
import test from 'node:test';

import type { AssetDragPlacementInput, ChangeSetGateway } from '../placement.ts';
import { createAssetPlacementPlan, submitPlacementChangeSet } from '../placement.ts';
import type { ProceduralGridRecipe } from '../recipes.ts';
import { compilePlacementRecipe } from '../recipes.ts';
import { DeterministicMockWorldMutationAdapter } from '../world-mutation-adapter.ts';
import { WorldAdapterError } from '../world-mutation-adapter.ts';
import { createWorldGraphUpdatePlan } from '../world-graph-plan.ts';
import { clone, readJson, readWorld } from './test-helpers.ts';

const scenePath = 'fixtures/remember-home/world.mock.json';

function placementInput(): AssetDragPlacementInput {
  const fixture = readJson<AssetDragPlacementInput & { mode: 'mock' }>(
    'fixtures/remember-home/key-placement-input.mock.json',
  );
  assert.equal(fixture.mode, 'mock');
  const { mode: _mode, ...input } = fixture;
  return input;
}

test('asset drag creates a complete reviewable ChangeSet plan without mutating the scene', async () => {
  const scene = readWorld(scenePath);
  const before = structuredClone(scene);
  const plan = createAssetPlacementPlan(scene, placementInput());

  assert.deepEqual(scene, before);
  assert.equal(plan.mode, 'planned');
  assert.equal(plan.dryRunRequired, true);
  assert.equal(plan.baseVersion, scene.sceneVersion);
  assert.equal(plan.targetObjectIds[0], 'sobj_home_key_variant');
  assert.equal(plan.proposedValues.object.asset?.assetId, 'asset_home_key_variant');
  assert.notEqual(plan.proposedValues.object.asset?.assetId, plan.proposedValues.object.sceneopsId);
  assert.deepEqual(plan.proposedValues.dropEvidence.worldPosition, [1.8, 0.8, 1.2]);
  assert.equal(plan.proposedValues.dropEvidence.camera.projection, 'perspective');
  assert.ok(plan.validationPlan.length > 0);
  assert.ok(plan.rollbackPlan.length > 0);
  assert.ok(plan.approvalRoles.length > 0);

  const gateway: ChangeSetGateway = {
    async create(received) {
      assert.strictEqual(received, plan);
      return { changeSetId: 'chg_key_placement_001', status: 'awaiting_approval', mode: 'mock' };
    },
  };
  const handle = await submitPlacementChangeSet(plan, gateway);
  assert.equal(handle.status, 'awaiting_approval');
  assert.equal(handle.mode, 'mock');
});

test('placement rejects stale bases, reused identity, and missing parent', () => {
  const scene = readWorld(scenePath);
  const stale = placementInput();
  stale.baseVersion = 'scnver_old';
  assert.throws(() => createAssetPlacementPlan(scene, stale), /STALE_SCENE_VERSION/);

  const reused = placementInput();
  reused.newSceneopsId = reused.asset.assetId;
  assert.throws(() => createAssetPlacementPlan(scene, reused), /cannot be reused/);

  const missingParent = placementInput();
  missingParent.parentSceneopsId = 'sobj_missing_parent';
  assert.throws(() => createAssetPlacementPlan(scene, missingParent), /parent does not exist/);
});

test('typed mock adapter requires approval, is idempotent, cancellable, and remains mock', async () => {
  const plan = createAssetPlacementPlan(readWorld(scenePath), placementInput());
  const adapter = new DeterministicMockWorldMutationAdapter();
  const approved = {
    commandId: 'cmd_place_key_001',
    correlationId: 'corr_place_key_001',
    changeSetId: 'chg_place_key_001',
    approvalId: 'approval_place_key_001',
    approvedBy: 'usr_level_lead',
    approvedAt: '2026-09-04T00:00:00Z',
    plan,
  };

  assert.equal((await adapter.healthCheck()).mode, 'mock');
  assert.equal((await adapter.capabilities()).mode, 'mock');
  const dryRun = await adapter.dryRun(approved);
  assert.equal(dryRun.mode, 'mock');

  const progress: number[] = [];
  const first = await adapter.execute(
    approved,
    new AbortController().signal,
    (event) => progress.push(event.progress),
  );
  const retry = await adapter.execute(approved, new AbortController().signal);
  assert.deepEqual(retry, first);
  assert.equal((await adapter.validate(first)).passed, true);
  assert.deepEqual(progress, [0.25, 0.75, 1]);
  assert.equal(first.provenance.changeSetId, approved.changeSetId);
  assert.equal((await adapter.rollback(first.snapshotId)).mode, 'mock');

  const cancelled = new AbortController();
  cancelled.abort();
  await assert.rejects(
    () => adapter.execute({ ...approved, commandId: 'cmd_cancelled' }, cancelled.signal),
    (error) => error instanceof WorldAdapterError && error.code === 'CANCELLED',
  );
  await assert.rejects(
    () => adapter.dryRun({ ...approved, approvalId: '' }),
    /APPROVAL_REQUIRED/,
  );
});

test('procedural placement is deterministic and requires version, seed, IDs, and constraints', () => {
  const scene = readWorld(scenePath);
  const recipe: ProceduralGridRecipe = {
    schemaVersion: 1,
    recipeId: 'recipe_key_markers',
    recipeVersion: '1.0.0',
    seed: 'find-my-way-home-demo-seed',
    constraints: ['Keep every marker inside the home hall zone.'],
    coordinateSystem: { units: 'meters', handedness: 'right', upAxis: 'Y', forwardAxis: '-Z' },
    kind: 'procedural-grid-v1',
    asset: { assetId: 'asset_marker', assetVersionId: 'assetver_marker_001' },
    instanceSceneopsIds: ['sobj_marker_01', 'sobj_marker_02', 'sobj_marker_03', 'sobj_marker_04'],
    namePrefix: 'RouteMarker',
    parentSceneopsId: 'sobj_home_root',
    origin: [-1, 0, 1],
    columns: 2,
    rows: 2,
    columnSpacingMeters: 1,
    rowSpacingMeters: 1.5,
    rotation: { x: 0, y: 0, z: 0, w: 1 },
    scale: [1, 1, 1],
    requirements: {
      colliderRequired: false,
      allowTriggerCollider: false,
      allowedScale: { minimum: [1, 1, 1], maximum: [1, 1, 1] },
      scaleSpace: 'world',
      interactions: [],
      navigationTarget: false,
    },
  };
  const first = compilePlacementRecipe(scene, recipe, 'unity');
  const second = compilePlacementRecipe(scene, clone(recipe), 'unity');
  assert.deepEqual(second, first);
  assert.equal(first.mode, 'planned');
  assert.equal(first.risk, 'high');
  assert.deepEqual(first.proposedValues.objects[3]?.transform.position, [0, 0, 2.5]);

  const noSeed = clone(recipe);
  noSeed.seed = '';
  assert.throws(() => compilePlacementRecipe(scene, noSeed, 'unity'), /seed/);
  const wrongIds = clone(recipe);
  wrongIds.instanceSceneopsIds.pop();
  assert.throws(() => compilePlacementRecipe(scene, wrongIds, 'unity'), /exactly 4/);
});

test('world graph, path, region, navigation, and lighting edits produce one scene-wide ChangeSet plan', () => {
  const scene = readWorld(scenePath);
  const proposedWorld = clone(scene.world);
  proposedWorld.lightingTargets[0]!.illuminanceLux = 220;
  proposedWorld.interactionRegions[0]!.size = [1.2, 1, 1.2];
  const plan = createWorldGraphUpdatePlan(scene, {
    baseVersion: scene.sceneVersion,
    proposedWorld,
    rationale: 'Improve key readability while preserving the approved route.',
    targetIntegration: 'unity',
  });
  assert.equal(plan.mutationKind, 'world.graph.update');
  assert.equal(plan.mode, 'planned');
  assert.equal((plan.previousValues?.world as typeof scene.world).lightingTargets[0]?.illuminanceLux, 180);
  assert.equal(plan.proposedValues.world.lightingTargets[0]?.illuminanceLux, 220);
  assert.ok(plan.targetObjectIds.includes('sobj_home_key'));

  assert.throws(
    () => createWorldGraphUpdatePlan(scene, {
      baseVersion: 'stale-version',
      proposedWorld,
      rationale: 'stale',
      targetIntegration: 'unity',
    }),
    /STALE_SCENE_VERSION/,
  );
});
