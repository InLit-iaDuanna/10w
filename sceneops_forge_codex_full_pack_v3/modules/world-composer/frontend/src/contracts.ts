import type {
  CameraPose as SceneViewerCameraPose,
  Vector3 as SceneViewerVector3,
} from '@sceneops/scene-viewer';

// Projection of the documented core execution-mode field; core-contracts remains its source of truth.
export type WorldExecutionMode = 'live' | 'cached' | 'mock' | 'planned' | 'blocked';

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export type Vector3 = SceneViewerVector3;
export type CameraPose = SceneViewerCameraPose;

export interface Quaternion {
  x: number;
  y: number;
  z: number;
  w: number;
}

export interface CanonicalCoordinateSystem {
  units: 'meters';
  handedness: 'right';
  upAxis: 'Y';
  forwardAxis: '-Z';
}

export const canonicalCoordinateSystem: CanonicalCoordinateSystem = {
  units: 'meters',
  handedness: 'right',
  upAxis: 'Y',
  forwardAxis: '-Z',
};

export interface Transform {
  position: Vector3;
  rotation: Quaternion;
  scale: Vector3;
}

export interface SceneObjectRef {
  sceneopsId: string;
  displayName: string;
}

export interface EvidenceRef {
  evidenceId: string;
  artifactId: string;
  mediaType: 'image' | 'video' | 'audio' | 'trace' | 'report';
  description: string;
  mode: WorldExecutionMode;
}

export interface AuthorRef {
  type: 'user' | 'agent';
  id: string;
  displayName: string;
}

interface SpatialContextBase {
  localPosition: Vector3;
  worldPosition: Vector3;
  localNormal: Vector3;
  worldNormal: Vector3;
  coordinateSystem: CanonicalCoordinateSystem;
}

export interface ObjectSpatialContext extends SpatialContextBase {
  reference: {
    kind: 'object';
    object: SceneObjectRef;
  };
}

export interface SceneSpatialContext extends SpatialContextBase {
  reference: {
    kind: 'scene';
    sceneId: string;
  };
}

export type SpatialContext = ObjectSpatialContext | SceneSpatialContext;

export type AnnotationType =
  | 'object-pin'
  | 'surface-pin'
  | 'point'
  | 'region-volume'
  | 'path-trace'
  | 'relation-link'
  | 'state'
  | 'sketch'
  | 'voice-draft';

export interface AnnotationContext {
  projectId: string;
  sceneId: string;
  sceneVersion: string;
  author: AuthorRef;
  createdAt: string;
  spatial: SpatialContext;
  camera: CameraPose;
  problem: string;
  intent: string;
  constraints: string[];
  acceptance: string[];
  evidence: EvidenceRef[];
  gameStateVersion: string;
  gameState: Record<string, JsonValue>;
  mode: WorldExecutionMode;
}

export interface ObjectPinDetails {
  kind: 'object-pin';
}

export interface SurfacePinDetails {
  kind: 'surface-pin';
  geometryVersion: string;
  triangleVertexIndices: [number, number, number];
  barycentric: [number, number, number];
}

export interface PointDetails {
  kind: 'point';
  label: string;
}

export interface RegionVolumeDetails {
  kind: 'region-volume';
  regionId: string;
  center: Vector3;
  size: Vector3;
  rotation: Quaternion;
}

export interface PathTraceDetails {
  kind: 'path-trace';
  pathId: string;
  points: SpatialPathPoint[];
}

export interface SpatialPathPoint {
  pointId: string;
  position: Vector3;
}

export interface RelationLinkDetails {
  kind: 'relation-link';
  relation: string;
  sourceSceneopsId: string;
  targetSceneopsId: string;
}

export interface StateDetails {
  kind: 'state';
  stateName: string;
  expectedValue: JsonValue;
}

export interface SketchStroke {
  strokeId: string;
  points: Vector3[];
  color: string;
  widthMeters: number;
}

export interface SketchDetails {
  kind: 'sketch';
  strokes: SketchStroke[];
}

export interface VoiceDraftDetails {
  kind: 'voice-draft';
  transcript: string;
  locale: string;
  transcriptionConfidence: number | null;
  audioEvidenceId?: string;
  draft: true;
}

export type AnnotationDetails =
  | ObjectPinDetails
  | SurfacePinDetails
  | PointDetails
  | RegionVolumeDetails
  | PathTraceDetails
  | RelationLinkDetails
  | StateDetails
  | SketchDetails
  | VoiceDraftDetails;

export interface WorldAnnotation {
  schemaVersion: 1;
  annotationId: string;
  type: AnnotationType;
  status: 'draft' | 'proposed' | 'open' | 'resolved' | 'archived' | 'rejected';
  context: AnnotationContext;
  details: AnnotationDetails;
}

export interface AssetVersionRef {
  assetId: string;
  assetVersionId: string;
}

export interface ScaleRange {
  minimum: Vector3;
  maximum: Vector3;
}

export interface RequiredInteraction {
  predicate: string;
  targetSceneopsId: string;
}

export interface SceneObjectRequirements {
  colliderRequired: boolean;
  allowTriggerCollider: boolean;
  allowedScale: ScaleRange;
  scaleSpace: 'local' | 'world';
  interactions: RequiredInteraction[];
  navigationTarget: boolean;
}

export interface WorldObjectRecord {
  sceneopsId: string;
  displayName: string;
  parentSceneopsId: string | null;
  asset?: AssetVersionRef;
  transform: Transform;
  collider: {
    shape: 'box' | 'sphere' | 'capsule' | 'mesh';
    enabled: boolean;
    isTrigger: boolean;
    sizeMeters: Vector3;
  } | null;
  spawnRadiusMeters: number | null;
  navigationNodeId: string | null;
  requirements: SceneObjectRequirements;
}

export interface WorldZone {
  zoneId: string;
  label: string;
  objectIds: string[];
}

export interface InteractionRegion {
  regionId: string;
  label: string;
  center: Vector3;
  size: Vector3;
  relatedSceneopsIds: string[];
}

export interface WorldPath {
  pathId: string;
  label: string;
  navNodeIds: string[];
  points: SpatialPathPoint[];
}

export interface WorldRelation {
  relationId: string;
  predicate: string;
  sourceSceneopsId: string;
  targetSceneopsId: string;
}

export interface LightingTarget {
  targetId: string;
  sceneopsId: string;
  illuminanceLux: number;
  colorTemperatureKelvin: number;
  intent: string;
}

export interface NavNode {
  nodeId: string;
  position: Vector3;
}

export interface NavMeshGraph {
  nodes: NavNode[];
  edges: Array<{ from: string; to: string; bidirectional: boolean }>;
}

export interface WorldGraph {
  zones: WorldZone[];
  interactionRegions: InteractionRegion[];
  paths: WorldPath[];
  relations: WorldRelation[];
  lightingTargets: LightingTarget[];
  navigation: NavMeshGraph;
}

export interface GateInputAvailability {
  state: 'available' | 'missing' | 'stale';
  sourceVersion: string | null;
  reason: string | null;
}

export interface WorldGateInputs {
  colliders: GateInputAvailability;
  navigation: GateInputAvailability & { agentProfileId: string | null };
  scalePolicy: GateInputAvailability;
  interactions: GateInputAvailability;
}

export interface WorldLevelDocument {
  schemaVersion: 1;
  projectId: string;
  sceneId: string;
  sceneVersion: string;
  coordinateSystem: CanonicalCoordinateSystem;
  mode: WorldExecutionMode;
  objects: WorldObjectRecord[];
  world: WorldGraph;
  gateInputs: WorldGateInputs;
}
