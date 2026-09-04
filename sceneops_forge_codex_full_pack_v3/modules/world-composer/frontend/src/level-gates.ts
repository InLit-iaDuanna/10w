import type {
  GateInputAvailability,
  NavMeshGraph,
  WorldObjectRecord,
  WorldLevelDocument,
  Vector3,
  WorldRelation,
} from './contracts.ts';
import { indexSceneObjects, validateWorldLevelDocument } from './world-model.ts';

export type LevelGateId =
  | 'missing-collider'
  | 'overlapping-spawn'
  | 'unreachable-target'
  | 'navmesh-break'
  | 'invalid-scale'
  | 'missing-interaction-relationship';

export interface LevelGateIssue {
  issueId: string;
  gateId: LevelGateId;
  severity: 'warning' | 'blocking';
  message: string;
  sceneopsIds: string[];
  pathId?: string;
  evidenceIds: string[];
}

export interface LevelGateResult {
  gateId: LevelGateId;
  status: 'pass' | 'fail' | 'blocked';
  sceneId: string;
  sceneVersion: string;
  mode: WorldLevelDocument['mode'];
  rule: string;
  issues: LevelGateIssue[];
  reason?: string;
}

export interface LevelGateReport {
  sceneId: string;
  sceneVersion: string;
  mode: WorldLevelDocument['mode'];
  passed: boolean;
  results: LevelGateResult[];
}

function issue(
  gateId: LevelGateId,
  suffix: string,
  message: string,
  sceneopsIds: string[],
  pathId?: string,
): LevelGateIssue {
  return {
    issueId: `world-gate:${gateId}:${suffix}`,
    gateId,
    severity: 'blocking',
    message,
    sceneopsIds,
    evidenceIds: [],
    ...(pathId ? { pathId } : {}),
  };
}

const gateRules: Record<LevelGateId, string> = {
  'missing-collider': 'Every collider-required object has an enabled, valid collider allowed by its policy.',
  'overlapping-spawn': 'Declared spherical spawn volumes must not overlap.',
  'unreachable-target': 'Every navigation target is reachable from at least one declared spawn for the agent profile.',
  'navmesh-break': 'Every consecutive node pair in each required path has a valid directed or bidirectional NavMesh edge.',
  'invalid-scale': 'Each object scale is finite, positive, and inside its explicit local or world scale policy.',
  'missing-interaction-relationship': 'Every required typed interaction has an existing source, predicate, and target.',
};

function result(
  snapshot: WorldLevelDocument,
  gateId: LevelGateId,
  issues: LevelGateIssue[],
): LevelGateResult {
  const ordered = [...issues].sort((left, right) => left.issueId.localeCompare(right.issueId));
  return {
    gateId,
    status: ordered.length === 0 ? 'pass' : 'fail',
    sceneId: snapshot.sceneId,
    sceneVersion: snapshot.sceneVersion,
    mode: snapshot.mode,
    rule: gateRules[gateId],
    issues: ordered,
  };
}

function blockedResult(
  snapshot: WorldLevelDocument,
  gateId: LevelGateId,
  input: GateInputAvailability,
  fallbackReason: string,
): LevelGateResult {
  return {
    gateId,
    status: 'blocked',
    sceneId: snapshot.sceneId,
    sceneVersion: snapshot.sceneVersion,
    mode: 'blocked',
    rule: gateRules[gateId],
    issues: [],
    reason: input.reason ?? fallbackReason,
  };
}

function missingColliderIssues(objects: readonly WorldObjectRecord[]): LevelGateIssue[] {
  return objects
    .filter((object) => {
      if (!object.requirements.colliderRequired) return false;
      if (!object.collider || !object.collider.enabled) return true;
      return object.collider.isTrigger && !object.requirements.allowTriggerCollider;
    })
    .map((object) =>
      issue(
        'missing-collider',
        object.sceneopsId,
        `${object.displayName} requires a collider.`,
        [object.sceneopsId],
      ),
    );
}

function distance(a: Vector3, b: Vector3): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

function overlappingSpawnIssues(objects: readonly WorldObjectRecord[]): LevelGateIssue[] {
  const spawns = objects.filter((object) => object.spawnRadiusMeters !== null);
  const issues: LevelGateIssue[] = [];
  for (let left = 0; left < spawns.length; left += 1) {
    for (let right = left + 1; right < spawns.length; right += 1) {
      const a = spawns[left];
      const b = spawns[right];
      if (!a || !b || a.spawnRadiusMeters === null || b.spawnRadiusMeters === null) continue;
      if (distance(a.transform.position, b.transform.position) < a.spawnRadiusMeters + b.spawnRadiusMeters) {
        issues.push(
          issue(
            'overlapping-spawn',
            `${a.sceneopsId}:${b.sceneopsId}`,
            `${a.displayName} overlaps ${b.displayName}.`,
            [a.sceneopsId, b.sceneopsId],
          ),
        );
      }
    }
  }
  return issues;
}

function adjacencyFor(graph: NavMeshGraph): Map<string, Set<string>> {
  const adjacency = new Map(graph.nodes.map((node) => [node.nodeId, new Set<string>()]));
  for (const edge of graph.edges) {
    adjacency.get(edge.from)?.add(edge.to);
    if (edge.bidirectional) adjacency.get(edge.to)?.add(edge.from);
  }
  return adjacency;
}

function reachableNodes(graph: NavMeshGraph, starts: string[]): Set<string> {
  const adjacency = adjacencyFor(graph);
  const reached = new Set<string>();
  const queue = starts.filter((nodeId) => adjacency.has(nodeId));
  while (queue.length > 0) {
    const current = queue.shift();
    if (!current || reached.has(current)) continue;
    reached.add(current);
    for (const next of adjacency.get(current) ?? []) {
      if (!reached.has(next)) queue.push(next);
    }
  }
  return reached;
}

function unreachableTargetIssues(snapshot: WorldLevelDocument): LevelGateIssue[] {
  const spawnNodes = snapshot.objects
    .filter((object) => object.spawnRadiusMeters !== null)
    .flatMap((object) => (object.navigationNodeId ? [object.navigationNodeId] : []));
  const reachable = reachableNodes(snapshot.world.navigation, spawnNodes);
  return snapshot.objects
    .filter((object) => object.requirements.navigationTarget)
    .filter((object) => !object.navigationNodeId || !reachable.has(object.navigationNodeId))
    .map((object) =>
      issue(
        'unreachable-target',
        object.sceneopsId,
        `${object.displayName} is not reachable from a declared spawn.`,
        [object.sceneopsId],
      ),
    );
}

function hasNavEdge(graph: NavMeshGraph, from: string, to: string): boolean {
  return graph.edges.some(
    (edge) =>
      (edge.from === from && edge.to === to) ||
      (edge.bidirectional && edge.from === to && edge.to === from),
  );
}

function navMeshBreakIssues(snapshot: WorldLevelDocument): LevelGateIssue[] {
  const nodeIds = new Set(snapshot.world.navigation.nodes.map((node) => node.nodeId));
  const issues: LevelGateIssue[] = [];
  snapshot.world.navigation.edges.forEach((edge, index) => {
    if (!nodeIds.has(edge.from) || !nodeIds.has(edge.to)) {
      issues.push(
        issue(
          'navmesh-break',
          `dangling-edge:${index}`,
          `NavMesh edge ${edge.from} -> ${edge.to} has a missing endpoint.`,
          [],
        ),
      );
    }
  });
  for (const path of snapshot.world.paths) {
    for (let index = 1; index < path.navNodeIds.length; index += 1) {
      const from = path.navNodeIds[index - 1];
      const to = path.navNodeIds[index];
      if (!from || !to || !nodeIds.has(from) || !nodeIds.has(to) || !hasNavEdge(snapshot.world.navigation, from, to)) {
        issues.push(
          issue(
            'navmesh-break',
            `${path.pathId}:${index - 1}`,
            `Path ${path.label} has no traversable NavMesh edge from ${from ?? '?'} to ${to ?? '?'}.`,
            [],
            path.pathId,
          ),
        );
      }
    }
  }
  return issues;
}

function scaleInside(value: Vector3, minimum: Vector3, maximum: Vector3): boolean {
  return ([0, 1, 2] as const).every(
    (axis) =>
      Number.isFinite(value[axis]) &&
      value[axis] > 0 &&
      value[axis] >= minimum[axis] &&
      value[axis] <= maximum[axis],
  );
}

function effectiveScale(
  object: WorldObjectRecord,
  objects: Map<string, WorldObjectRecord>,
): Vector3 {
  const scale: [number, number, number] = [...object.transform.scale];
  let parentId = object.parentSceneopsId;
  while (parentId) {
    const parent = objects.get(parentId);
    if (!parent) break;
    scale[0] *= parent.transform.scale[0];
    scale[1] *= parent.transform.scale[1];
    scale[2] *= parent.transform.scale[2];
    parentId = parent.parentSceneopsId;
  }
  return scale;
}

function invalidScaleIssues(objectsList: readonly WorldObjectRecord[]): LevelGateIssue[] {
  const objects = indexSceneObjects(objectsList);
  return [...objects.values()]
    .filter(
      (object) =>
        !scaleInside(
          object.requirements.scaleSpace === 'world'
            ? effectiveScale(object, objects)
            : object.transform.scale,
          object.requirements.allowedScale.minimum,
          object.requirements.allowedScale.maximum,
        ),
    )
    .map((object) =>
      issue(
        'invalid-scale',
        object.sceneopsId,
        `${object.displayName} is outside its declared scale range.`,
        [object.sceneopsId],
      ),
    );
}

function relationExists(relations: readonly WorldRelation[], source: string, predicate: string, target: string): boolean {
  return relations.some(
    (relation) =>
      relation.sourceSceneopsId === source &&
      relation.predicate === predicate &&
      relation.targetSceneopsId === target,
  );
}

function missingInteractionIssues(snapshot: WorldLevelDocument): LevelGateIssue[] {
  const objects = indexSceneObjects(snapshot.objects);
  const issues: LevelGateIssue[] = [];
  for (const object of objects.values()) {
    for (const required of object.requirements.interactions) {
      if (!objects.has(required.targetSceneopsId)) {
        issues.push(
          issue(
            'missing-interaction-relationship',
            `${object.sceneopsId}:${required.predicate}:missing-target`,
            `${object.displayName} references a missing interaction target.`,
            [object.sceneopsId, required.targetSceneopsId],
          ),
        );
      } else if (!relationExists(snapshot.world.relations, object.sceneopsId, required.predicate, required.targetSceneopsId)) {
        issues.push(
          issue(
            'missing-interaction-relationship',
            `${object.sceneopsId}:${required.predicate}:${required.targetSceneopsId}`,
            `${object.displayName} is missing relationship ${required.predicate}.`,
            [object.sceneopsId, required.targetSceneopsId],
          ),
        );
      }
    }
  }
  return issues;
}

export function validateLevel(snapshot: WorldLevelDocument): LevelGateReport {
  validateWorldLevelDocument(snapshot);
  const colliderUnavailable = snapshot.gateInputs.colliders.state !== 'available';
  const navigationUnavailable =
    snapshot.gateInputs.navigation.state !== 'available' ||
    !snapshot.gateInputs.navigation.agentProfileId;
  const scaleUnavailable = snapshot.gateInputs.scalePolicy.state !== 'available';
  const interactionUnavailable = snapshot.gateInputs.interactions.state !== 'available';
  const results = [
    colliderUnavailable
      ? blockedResult(snapshot, 'missing-collider', snapshot.gateInputs.colliders, 'Collider snapshot unavailable')
      : result(snapshot, 'missing-collider', missingColliderIssues(snapshot.objects)),
    colliderUnavailable
      ? blockedResult(snapshot, 'overlapping-spawn', snapshot.gateInputs.colliders, 'Spawn volumes unavailable')
      : result(snapshot, 'overlapping-spawn', overlappingSpawnIssues(snapshot.objects)),
    navigationUnavailable
      ? blockedResult(
          snapshot,
          'unreachable-target',
          snapshot.gateInputs.navigation,
          'Navigation snapshot or agent profile unavailable',
        )
      : result(snapshot, 'unreachable-target', unreachableTargetIssues(snapshot)),
    navigationUnavailable
      ? blockedResult(
          snapshot,
          'navmesh-break',
          snapshot.gateInputs.navigation,
          'Navigation snapshot or agent profile unavailable',
        )
      : result(snapshot, 'navmesh-break', navMeshBreakIssues(snapshot)),
    scaleUnavailable
      ? blockedResult(snapshot, 'invalid-scale', snapshot.gateInputs.scalePolicy, 'Scale policy unavailable')
      : result(snapshot, 'invalid-scale', invalidScaleIssues(snapshot.objects)),
    interactionUnavailable
      ? blockedResult(
          snapshot,
          'missing-interaction-relationship',
          snapshot.gateInputs.interactions,
          'Interaction snapshot unavailable',
        )
      : result(snapshot, 'missing-interaction-relationship', missingInteractionIssues(snapshot)),
  ];
  return {
    sceneId: snapshot.sceneId,
    sceneVersion: snapshot.sceneVersion,
    mode: snapshot.mode,
    passed: results.every((gate) => gate.status === 'pass'),
    results,
  };
}
