import { assertCameraPose } from '@sceneops/scene-viewer';
import {
  canonicalCoordinateSystem,
  type AnnotationDetails,
  type AnnotationType,
  type CanonicalCoordinateSystem,
  type Quaternion,
  type Vector3,
  type WorldAnnotation,
} from './contracts.ts';
import { isWorldExecutionMode } from './execution.ts';

const annotationTypes: ReadonlySet<string> = new Set([
  'object-pin',
  'surface-pin',
  'point',
  'region-volume',
  'path-trace',
  'relation-link',
  'state',
  'sketch',
  'voice-draft',
]);

function assertNonEmpty(value: string, field: string): void {
  if (!value.trim()) throw new Error(`${field} is required`);
}

function assertFiniteVector(value: Vector3, field: string): void {
  if (value.length !== 3 || !value.every(Number.isFinite)) {
    throw new Error(`${field} must contain finite numbers`);
  }
}

function assertUnitNormal(normal: Vector3, field: string): void {
  assertFiniteVector(normal, field);
  const magnitude = Math.hypot(...normal);
  if (Math.abs(magnitude - 1) > 1e-6) throw new Error(`${field} must be normalized`);
}

function assertUnitQuaternion(rotation: Quaternion, field: string): void {
  if (![rotation.x, rotation.y, rotation.z, rotation.w].every(Number.isFinite)) {
    throw new Error(`${field} must contain finite numbers`);
  }
  const magnitude = Math.hypot(rotation.x, rotation.y, rotation.z, rotation.w);
  if (Math.abs(magnitude - 1) > 1e-6) throw new Error(`${field} must be normalized`);
}

function hasCanonicalCoordinates(value: CanonicalCoordinateSystem): boolean {
  return (
    value.units === canonicalCoordinateSystem.units &&
    value.handedness === canonicalCoordinateSystem.handedness &&
    value.upAxis === canonicalCoordinateSystem.upAxis &&
    value.forwardAxis === canonicalCoordinateSystem.forwardAxis
  );
}

function assertUtcTimestamp(timestamp: string): void {
  if (!timestamp.endsWith('Z') || Number.isNaN(Date.parse(timestamp))) {
    throw new Error('createdAt must be a UTC ISO-8601 timestamp');
  }
}

function validateDetails(type: AnnotationType, details: AnnotationDetails): void {
  if (type !== details.kind) throw new Error('Annotation type and details kind must match');
  if (details.kind === 'region-volume') {
    assertNonEmpty(details.regionId, 'regionId');
    assertFiniteVector(details.center, 'region center');
    assertFiniteVector(details.size, 'region size');
    if (details.size.some((component) => component <= 0)) {
      throw new Error('Region size must be positive');
    }
    assertUnitQuaternion(details.rotation, 'region rotation');
  }
  if (details.kind === 'path-trace' && details.points.length < 2) {
    throw new Error('A path trace needs at least two points');
  }
  if (details.kind === 'path-trace') {
    assertNonEmpty(details.pathId, 'pathId');
    const pointIds = new Set<string>();
    details.points.forEach((point, index) => {
      assertNonEmpty(point.pointId, `path point ${index} ID`);
      if (pointIds.has(point.pointId)) throw new Error('Path point IDs must be unique');
      pointIds.add(point.pointId);
      assertFiniteVector(point.position, `path point ${index}`);
      if (index > 0) {
        const previous = details.points[index - 1];
        if (previous && previous.position.every((value, axis) => value === point.position[axis])) {
          throw new Error('Consecutive path points must not be identical');
        }
      }
    });
  }
  if (details.kind === 'point') assertNonEmpty(details.label, 'point label');
  if (details.kind === 'relation-link') {
    assertNonEmpty(details.relation, 'relation');
    assertNonEmpty(details.sourceSceneopsId, 'relation source');
    assertNonEmpty(details.targetSceneopsId, 'relation target');
    if (details.sourceSceneopsId === details.targetSceneopsId) {
      throw new Error('Relation endpoints must be distinct');
    }
  }
  if (details.kind === 'sketch') {
    if (details.strokes.length === 0) throw new Error('A sketch needs at least one stroke');
    const strokeIds = new Set<string>();
    for (const stroke of details.strokes) {
      assertNonEmpty(stroke.strokeId, 'stroke ID');
      if (strokeIds.has(stroke.strokeId)) throw new Error('Sketch stroke IDs must be unique');
      strokeIds.add(stroke.strokeId);
      assertNonEmpty(stroke.color, 'stroke color');
      if (!Number.isFinite(stroke.widthMeters) || stroke.widthMeters <= 0) {
        throw new Error('Sketch width must be positive');
      }
      if (stroke.points.length < 2) throw new Error('A sketch stroke needs at least two points');
      stroke.points.forEach((point, index) => assertFiniteVector(point, `sketch point ${index}`));
    }
  }
  if (details.kind === 'state') assertNonEmpty(details.stateName, 'state name');
  if (details.kind === 'surface-pin') {
    assertNonEmpty(details.geometryVersion, 'geometryVersion');
    if (details.triangleVertexIndices.some((index) => !Number.isInteger(index) || index < 0)) {
      throw new Error('Surface triangle indices must be non-negative integers');
    }
    if (details.barycentric.some((weight) => !Number.isFinite(weight) || weight < 0 || weight > 1)) {
      throw new Error('Surface barycentric weights are invalid');
    }
    const total = details.barycentric.reduce((sum, weight) => sum + weight, 0);
    if (Math.abs(total - 1) > 1e-6) throw new Error('Surface barycentric weights must sum to one');
  }
  if (details.kind === 'voice-draft') {
    assertNonEmpty(details.transcript, 'voice transcript');
    assertNonEmpty(details.locale, 'voice locale');
    if (
      details.transcriptionConfidence !== null &&
      (!Number.isFinite(details.transcriptionConfidence) ||
        details.transcriptionConfidence < 0 ||
        details.transcriptionConfidence > 1)
    ) {
      throw new Error('Voice transcription confidence must be between zero and one');
    }
    if (details.draft !== true) throw new Error('Voice annotation payload must be a draft');
  }
}

export function validateAnnotation(annotation: WorldAnnotation): void {
  if (annotation.schemaVersion !== 1) throw new Error('Unsupported annotation schema version');
  if (!annotationTypes.has(annotation.type)) throw new Error('Unknown annotation type');
  assertNonEmpty(annotation.annotationId, 'annotationId');
  assertNonEmpty(annotation.context.projectId, 'projectId');
  assertNonEmpty(annotation.context.sceneId, 'sceneId');
  assertNonEmpty(annotation.context.sceneVersion, 'sceneVersion');
  if (!['draft', 'proposed', 'open', 'resolved', 'archived', 'rejected'].includes(annotation.status)) {
    throw new Error('Invalid annotation status');
  }
  assertNonEmpty(annotation.context.author.id, 'author id');
  assertNonEmpty(annotation.context.author.displayName, 'author display name');
  assertUtcTimestamp(annotation.context.createdAt);
  if (annotation.context.spatial.reference.kind === 'object') {
    assertNonEmpty(annotation.context.spatial.reference.object.sceneopsId, 'sceneops_id');
    assertNonEmpty(annotation.context.spatial.reference.object.displayName, 'object display name');
  } else {
    assertNonEmpty(annotation.context.spatial.reference.sceneId, 'spatial sceneId');
  }
  assertFiniteVector(annotation.context.spatial.localPosition, 'local position');
  assertFiniteVector(annotation.context.spatial.worldPosition, 'world position');
  assertUnitNormal(annotation.context.spatial.localNormal, 'local normal');
  assertUnitNormal(annotation.context.spatial.worldNormal, 'world normal');
  assertCameraPose(annotation.context.camera);
  if (
    !hasCanonicalCoordinates(annotation.context.spatial.coordinateSystem) ||
    annotation.context.camera.units !== 'meters' ||
    annotation.context.camera.axisConvention !== 'right-handed-y-up'
  ) {
    throw new Error('Annotation spatial and camera frames must be canonical');
  }
  if (!isWorldExecutionMode(annotation.context.mode)) throw new Error('Invalid execution mode');
  assertNonEmpty(annotation.context.problem, 'problem');
  assertNonEmpty(annotation.context.intent, 'intent');
  assertNonEmpty(annotation.context.gameStateVersion, 'gameStateVersion');
  if (annotation.context.acceptance.length === 0) {
    throw new Error('At least one acceptance statement is required');
  }
  for (const evidence of annotation.context.evidence) {
    assertNonEmpty(evidence.evidenceId, 'evidenceId');
    assertNonEmpty(evidence.artifactId, 'artifactId');
    assertNonEmpty(evidence.description, 'evidence description');
    if (!isWorldExecutionMode(evidence.mode)) throw new Error('Invalid evidence execution mode');
  }
  if (
    ['object-pin', 'surface-pin', 'relation-link'].includes(annotation.type) &&
    annotation.context.spatial.reference.kind !== 'object'
  ) {
    throw new Error(`${annotation.type} requires an object spatial reference`);
  }
  validateDetails(annotation.type, annotation.details);
  if (annotation.details.kind === 'voice-draft' && annotation.status !== 'draft') {
    throw new Error('Voice annotations must remain drafts until reviewed');
  }
}

export function serializeAnnotation(annotation: WorldAnnotation): string {
  validateAnnotation(annotation);
  return JSON.stringify(annotation);
}

export function restoreAnnotation(serialized: string): WorldAnnotation {
  let value: unknown;
  try {
    value = JSON.parse(serialized);
  } catch {
    throw new Error('Annotation is not valid JSON');
  }
  const annotation = value as WorldAnnotation;
  validateAnnotation(annotation);
  return structuredClone(annotation);
}
