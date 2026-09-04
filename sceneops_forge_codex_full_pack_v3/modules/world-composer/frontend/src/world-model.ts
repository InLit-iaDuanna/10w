import {
  canonicalCoordinateSystem,
  type WorldObjectRecord,
  type WorldLevelDocument,
  type Vector3,
} from './contracts.ts';
import { isWorldExecutionMode } from './execution.ts';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFiniteVector(value: unknown): value is Vector3 {
  return (
    Array.isArray(value) &&
    value.length === 3 &&
    value.every((component) => typeof component === 'number' && Number.isFinite(component))
  );
}

export function indexSceneObjects(objects: readonly WorldObjectRecord[]): Map<string, WorldObjectRecord> {
  const index = new Map<string, WorldObjectRecord>();
  for (const object of objects) {
    if (index.has(object.sceneopsId)) {
      throw new Error(`Duplicate sceneops_id: ${object.sceneopsId}`);
    }
    index.set(object.sceneopsId, object);
  }
  return index;
}

function hasCanonicalCoordinates(value: unknown): boolean {
  return (
    isRecord(value) &&
    value.units === canonicalCoordinateSystem.units &&
    value.handedness === canonicalCoordinateSystem.handedness &&
    value.upAxis === canonicalCoordinateSystem.upAxis &&
    value.forwardAxis === canonicalCoordinateSystem.forwardAxis
  );
}

function assertParentGraphIsAcyclic(objects: Map<string, WorldObjectRecord>): void {
  for (const object of objects.values()) {
    const visited = new Set<string>([object.sceneopsId]);
    let parentId = object.parentSceneopsId;
    while (parentId) {
      if (visited.has(parentId)) throw new Error(`Parent cycle includes ${parentId}`);
      visited.add(parentId);
      parentId = objects.get(parentId)?.parentSceneopsId ?? null;
    }
  }
}

function isUnitQuaternion(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const x = value.x;
  const y = value.y;
  const z = value.z;
  const w = value.w;
  if (![x, y, z, w].every((component) => typeof component === 'number' && Number.isFinite(component))) {
    return false;
  }
  return Math.abs(Math.hypot(x as number, y as number, z as number, w as number) - 1) <= 1e-6;
}

function validateAvailability(snapshot: WorldLevelDocument): void {
  if (!isRecord(snapshot.gateInputs)) {
    throw new Error('Gate input availability is required');
  }
  const required = ['colliders', 'navigation', 'scalePolicy', 'interactions'] as const;
  const provided = Object.keys(snapshot.gateInputs);
  if (
    required.some((name) => !snapshot.gateInputs[name]) ||
    provided.some((name) => !required.includes(name as (typeof required)[number]))
  ) {
    throw new Error('All gate input availability records are required');
  }
  for (const [name, input] of Object.entries(snapshot.gateInputs)) {
    if (!isRecord(input)) throw new Error(`Invalid gate input availability for ${name}`);
    const state = input.state;
    const sourceVersion = input.sourceVersion;
    const reason = input.reason;
    if (typeof state !== 'string' || !['available', 'missing', 'stale'].includes(state)) {
      throw new Error(`Invalid gate input state for ${name}`);
    }
    if (sourceVersion !== null && typeof sourceVersion !== 'string') {
      throw new Error(`Invalid gate input source version for ${name}`);
    }
    if (reason !== null && typeof reason !== 'string') {
      throw new Error(`Invalid gate input reason for ${name}`);
    }
    if (state === 'available' && sourceVersion !== snapshot.sceneVersion) {
      throw new Error(`Available gate input ${name} must match the scene version`);
    }
    if (state !== 'available' && (typeof reason !== 'string' || !reason.trim())) {
      throw new Error(`Unavailable gate input ${name} requires a reason`);
    }
  }
  const agentProfileId = snapshot.gateInputs.navigation.agentProfileId;
  if (agentProfileId !== null && (typeof agentProfileId !== 'string' || !agentProfileId.trim())) {
    throw new Error('Navigation agent profile must be a non-empty ID or null');
  }
}

function assertUnique(values: string[], label: string): void {
  if (values.some((value) => !value.trim())) throw new Error(`${label} IDs must be non-empty`);
  if (new Set(values).size !== values.length) throw new Error(`${label} IDs must be unique`);
}

function validateWorldGraph(snapshot: WorldLevelDocument, objects: Map<string, WorldObjectRecord>): void {
  const graph = snapshot.world;
  if (
    !graph ||
    !Array.isArray(graph.zones) ||
    !Array.isArray(graph.interactionRegions) ||
    !Array.isArray(graph.paths) ||
    !Array.isArray(graph.relations) ||
    !Array.isArray(graph.lightingTargets) ||
    !graph.navigation ||
    !Array.isArray(graph.navigation.nodes) ||
    !Array.isArray(graph.navigation.edges)
  ) {
    throw new Error('World graph collections are required');
  }
  assertUnique(graph.zones.map((zone) => zone.zoneId), 'Zone');
  assertUnique(graph.interactionRegions.map((region) => region.regionId), 'Interaction region');
  assertUnique(graph.paths.map((path) => path.pathId), 'Path');
  assertUnique(graph.relations.map((relation) => relation.relationId), 'Relation');
  assertUnique(graph.lightingTargets.map((target) => target.targetId), 'Lighting target');
  assertUnique(graph.navigation.nodes.map((node) => node.nodeId), 'Navigation node');

  for (const zone of graph.zones) {
    if (zone.objectIds.some((id) => !objects.has(id))) throw new Error(`Zone ${zone.zoneId} has a missing object`);
  }
  for (const region of graph.interactionRegions) {
    if (!validPositiveVector(region.size) || !isFiniteVector(region.center)) {
      throw new Error(`Interaction region ${region.regionId} has invalid bounds`);
    }
    if (region.relatedSceneopsIds.some((id) => !objects.has(id))) {
      throw new Error(`Interaction region ${region.regionId} has a missing object`);
    }
  }
  for (const path of graph.paths) {
    if (path.points.length < 2 || path.navNodeIds.length < 2) {
      throw new Error(`Path ${path.pathId} requires at least two points and NavMesh nodes`);
    }
    assertUnique(path.points.map((point) => point.pointId), `Path ${path.pathId} point`);
    path.points.forEach((point) => {
      if (!isFiniteVector(point.position)) throw new Error(`Path ${path.pathId} has an invalid point`);
    });
  }
  for (const relation of graph.relations) {
    if (!relation.predicate.trim()) throw new Error(`Relation ${relation.relationId} requires a predicate`);
  }
  for (const target of graph.lightingTargets) {
    if (!objects.has(target.sceneopsId)) throw new Error(`Lighting target ${target.targetId} has a missing object`);
    if (
      !Number.isFinite(target.illuminanceLux) ||
      target.illuminanceLux < 0 ||
      !Number.isFinite(target.colorTemperatureKelvin) ||
      target.colorTemperatureKelvin <= 0
    ) {
      throw new Error(`Lighting target ${target.targetId} has invalid values`);
    }
  }
  graph.navigation.nodes.forEach((node) => {
    if (!isFiniteVector(node.position)) throw new Error(`Navigation node ${node.nodeId} has an invalid position`);
  });
}

function validPositiveVector(value: Vector3): boolean {
  return isFiniteVector(value) && value.every((component) => component > 0);
}

function validateScaleRange(object: WorldObjectRecord): void {
  const range = object.requirements.allowedScale;
  if (!validPositiveVector(range.minimum) || !validPositiveVector(range.maximum)) {
    throw new Error(`Invalid scale policy for ${object.sceneopsId}`);
  }
  if (
    range.minimum[0] > range.maximum[0] ||
    range.minimum[1] > range.maximum[1] ||
    range.minimum[2] > range.maximum[2]
  ) {
    throw new Error(`Inverted scale policy for ${object.sceneopsId}`);
  }
}

export function validateWorldLevelDocument(snapshot: WorldLevelDocument): void {
  if (snapshot.schemaVersion !== 1) throw new Error('Unsupported scene schema version');
  if (!snapshot.projectId || !snapshot.sceneId || !snapshot.sceneVersion) {
    throw new Error('Scene identity and version are required');
  }
  if (!isWorldExecutionMode(snapshot.mode)) throw new Error('Invalid scene execution mode');
  validateAvailability(snapshot);
  if (!hasCanonicalCoordinates(snapshot.coordinateSystem)) {
    throw new Error('Scene must use the canonical coordinate system');
  }

  const objects = indexSceneObjects(snapshot.objects);
  for (const object of objects.values()) {
    if (!object.sceneopsId || !object.displayName.trim()) throw new Error('Scene object identity is required');
    if (
      !isFiniteVector(object.transform.position) ||
      !isFiniteVector(object.transform.scale) ||
      !isUnitQuaternion(object.transform.rotation)
    ) {
      throw new Error(`Invalid transform for ${object.sceneopsId}`);
    }
    if (object.transform.scale.some((axis) => axis === 0)) {
      throw new Error(`Singular transform for ${object.sceneopsId}`);
    }
    validateScaleRange(object);
    if (object.collider && !validPositiveVector(object.collider.sizeMeters)) {
      throw new Error(`Invalid collider bounds for ${object.sceneopsId}`);
    }
    if (
      object.spawnRadiusMeters !== null &&
      (!Number.isFinite(object.spawnRadiusMeters) || object.spawnRadiusMeters <= 0)
    ) {
      throw new Error(`Invalid spawn radius for ${object.sceneopsId}`);
    }
    if (object.parentSceneopsId && !objects.has(object.parentSceneopsId)) {
      throw new Error(`Missing parent ${object.parentSceneopsId}`);
    }
    if (object.asset && object.asset.assetId === object.sceneopsId) {
      throw new Error('Asset identity and scene instance identity must remain distinct');
    }
    for (const interaction of object.requirements.interactions) {
      if (!interaction.predicate.trim() || !interaction.targetSceneopsId.trim()) {
        throw new Error(`Invalid interaction requirement for ${object.sceneopsId}`);
      }
    }
  }
  assertParentGraphIsAcyclic(objects);
  validateWorldGraph(snapshot, objects);
}

export function parseWorldLevelDocument(value: unknown): WorldLevelDocument {
  if (!isRecord(value) || !Array.isArray(value.objects) || !isRecord(value.world)) {
    throw new Error('Invalid scene snapshot');
  }
  const snapshot = value as unknown as WorldLevelDocument;
  validateWorldLevelDocument(snapshot);
  return structuredClone(snapshot);
}
