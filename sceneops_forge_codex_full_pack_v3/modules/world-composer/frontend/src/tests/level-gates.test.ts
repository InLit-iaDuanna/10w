import assert from 'node:assert/strict';
import test from 'node:test';

import type { LevelGateId } from '../level-gates.ts';
import { validateLevel } from '../level-gates.ts';
import { parseWorldLevelDocument, validateWorldLevelDocument } from '../world-model.ts';
import { clone, readJson, readWorld } from './test-helpers.ts';

const homePath = 'fixtures/remember-home/world.mock.json';
const warehousePath = 'fixtures/warehouse-escape/world.mock.json';

test('both deterministic demo projects pass all six level gates as mock', () => {
  for (const path of [homePath, warehousePath]) {
    const scene = parseWorldLevelDocument(readWorld(path));
    const report = validateLevel(scene);
    assert.equal(report.mode, 'mock');
    assert.equal(report.passed, true);
    assert.equal(report.results.length, 6);
    assert.ok(report.results.every((result) => result.status === 'pass'));
  }
});

test('detects each required representative failure with stable IDs', () => {
  const base = readWorld(homePath);

  const noCollider = clone(base);
  noCollider.objects.find((object) => object.sceneopsId === 'sobj_home_key')!.collider = null;
  assert.equal(validateLevel(noCollider).results[0]?.status, 'fail');

  const overlapping = clone(base);
  const spawn = clone(overlapping.objects.find((object) => object.sceneopsId === 'sobj_player_spawn')!);
  spawn.sceneopsId = 'sobj_player_spawn_secondary';
  spawn.displayName = 'SecondarySpawn';
  overlapping.objects.push(spawn);
  assert.equal(gateFrom(overlapping, 'overlapping-spawn').status, 'fail');

  const unreachable = clone(base);
  unreachable.world.navigation.edges = [];
  assert.equal(gateFrom(unreachable, 'unreachable-target').status, 'fail');

  const brokenPath = clone(base);
  brokenPath.world.navigation.edges = brokenPath.world.navigation.edges.slice(0, 1);
  const pathGate = gateFrom(brokenPath, 'navmesh-break');
  assert.equal(pathGate.status, 'fail');
  assert.equal(pathGate.issues[0]?.pathId, 'path_find_key_and_home');

  const invalidScale = clone(base);
  invalidScale.objects.find((object) => object.sceneopsId === 'sobj_home_key')!.transform.scale = [4, 4, 4];
  assert.equal(gateFrom(invalidScale, 'invalid-scale').status, 'fail');

  const missingRelation = clone(base);
  missingRelation.world.relations = [];
  assert.equal(gateFrom(missingRelation, 'missing-interaction-relationship').status, 'fail');
});

function gateFrom(scene: ReturnType<typeof readWorld>, gateId: LevelGateId) {
  const result = validateLevel(scene).results.find((candidate) => candidate.gateId === gateId);
  assert.ok(result);
  return result;
}

test('the warehouse NavMesh issue fixture deterministically removes the expected edge', () => {
  const fixture = readIssueFixture();
  const warehouse = clone(readWorld(warehousePath));
  warehouse.world.navigation.edges = warehouse.world.navigation.edges.filter(
    (edge) =>
      edge.from !== fixture.mutation.removeNavEdge.from ||
      edge.to !== fixture.mutation.removeNavEdge.to,
  );
  const result = gateFrom(warehouse, fixture.expected.gateId);
  assert.equal(fixture.mode, 'mock');
  assert.equal(result.status, fixture.expected.status);
  assert.equal(result.issues[0]?.pathId, fixture.expected.pathId);
});

function readIssueFixture(): {
  mode: 'mock';
  mutation: { removeNavEdge: { from: string; to: string } };
  expected: { gateId: LevelGateId; status: 'fail'; pathId: string };
} {
  return readJson('fixtures/issues/navmesh-path-break.mock.json');
}

test('reports missing or stale gate inputs as blocked instead of guessing pass', () => {
  const scene = clone(readWorld(homePath));
  scene.gateInputs.navigation = {
    state: 'missing',
    sourceVersion: null,
    reason: 'Unity NavMesh adapter is not connected.',
    agentProfileId: null,
  };
  const report = validateLevel(scene);
  assert.equal(report.passed, false);
  assert.equal(gateFrom(scene, 'unreachable-target').status, 'blocked');
  assert.equal(gateFrom(scene, 'navmesh-break').mode, 'blocked');
});

test('orders gate issues deterministically and rejects invalid hierarchy documents', () => {
  const scene = clone(readWorld(homePath));
  const entrance = scene.objects.find((object) => object.sceneopsId === 'sobj_home_entrance')!;
  const key = scene.objects.find((object) => object.sceneopsId === 'sobj_home_key')!;
  entrance.collider = null;
  key.collider = null;
  scene.objects.reverse();
  const issues = gateFrom(scene, 'missing-collider').issues.map((entry) => entry.issueId);
  assert.deepEqual(issues, [...issues].sort());

  const cycle = clone(readWorld(homePath));
  cycle.objects.find((object) => object.sceneopsId === 'sobj_home_root')!.parentSceneopsId = 'sobj_home_key';
  assert.throws(() => validateWorldLevelDocument(cycle), /Parent cycle/);

  const incompleteGraph = clone(readWorld(homePath));
  Reflect.deleteProperty(incompleteGraph.world, 'relations');
  assert.throws(
    () => validateWorldLevelDocument(incompleteGraph),
    /World graph collections are required/,
  );

  const invalidAvailability = clone(readWorld(homePath));
  invalidAvailability.gateInputs.navigation.agentProfileId = '';
  assert.throws(
    () => validateWorldLevelDocument(invalidAvailability),
    /Navigation agent profile/,
  );
});
