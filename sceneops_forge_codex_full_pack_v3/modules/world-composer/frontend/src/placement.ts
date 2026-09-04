import { assertCameraPose } from '@sceneops/scene-viewer';
import type {
  AssetVersionRef,
  CameraPose,
  WorldExecutionMode,
  SceneObjectRequirements,
  Transform,
  Vector3,
  WorldLevelDocument,
  WorldObjectRecord,
} from './contracts.ts';
import { indexSceneObjects, validateWorldLevelDocument } from './world-model.ts';

export type WorldMutationKind =
  | 'world.scene-object.place'
  | 'world.graybox.apply'
  | 'world.procedural-placement.apply'
  | 'world.graph.update'
  | 'world.lighting-target.apply';

export interface WorldMutationPlan<TProposed> {
  schemaVersion: 1;
  mutationKind: WorldMutationKind;
  baseVersion: string;
  targetModule: 'world-composer';
  targetIntegration: 'scene-store' | 'blender' | 'unity';
  targetSceneId: string;
  targetObjectIds: string[];
  previousValues: null | Record<string, unknown>;
  proposedValues: TProposed;
  rationale: string;
  expectedResult: string;
  impactScope: string[];
  risk: 'low' | 'medium' | 'high';
  validationPlan: string[];
  rollbackPlan: string[];
  approvalRoles: string[];
  dryRunRequired: true;
  mode: 'planned';
}

export interface ChangeSetHandle {
  changeSetId: string;
  status: 'draft' | 'planned' | 'awaiting_approval';
  mode: WorldExecutionMode;
}

export interface ChangeSetGateway {
  create<TProposed>(plan: WorldMutationPlan<TProposed>): Promise<ChangeSetHandle>;
}

export interface AssetDragPlacementInput {
  baseVersion: string;
  asset: AssetVersionRef;
  newSceneopsId: string;
  displayName: string;
  parentSceneopsId: string | null;
  worldPosition: Vector3;
  worldNormal: Vector3;
  dropRayOrigin: Vector3;
  dropRayDirection: Vector3;
  camera: CameraPose;
  rotation: Transform['rotation'];
  scale: Vector3;
  collider: WorldObjectRecord['collider'];
  requirements: SceneObjectRequirements;
  rationale: string;
  targetIntegration: WorldMutationPlan<unknown>['targetIntegration'];
}

export interface PlacementProposal {
  object: WorldObjectRecord;
  dropEvidence: {
    worldPosition: Vector3;
    surfaceNormal: Vector3;
    rayOrigin: Vector3;
    rayDirection: Vector3;
    camera: CameraPose;
  };
}

function assertFiniteVector(value: Vector3, name: string): void {
  if (value.length !== 3 || !value.every(Number.isFinite)) {
    throw new Error(`${name} must contain finite values`);
  }
}

function assertUnitVector(value: Vector3, name: string): void {
  assertFiniteVector(value, name);
  if (Math.abs(Math.hypot(...value) - 1) > 1e-6) {
    throw new Error(`${name} must be normalized`);
  }
}

export function createAssetPlacementPlan(
  scene: WorldLevelDocument,
  input: AssetDragPlacementInput,
): WorldMutationPlan<PlacementProposal> {
  validateWorldLevelDocument(scene);
  if (scene.sceneVersion !== input.baseVersion) throw new Error('STALE_SCENE_VERSION');
  if (!input.asset.assetId || !input.asset.assetVersionId) throw new Error('Asset version identity is required');
  if (!input.newSceneopsId) throw new Error('A core-issued sceneops_id is required');
  if (input.asset.assetId === input.newSceneopsId) {
    throw new Error('Asset identity cannot be reused as scene instance identity');
  }
  const objectIndex = indexSceneObjects(scene.objects);
  if (objectIndex.has(input.newSceneopsId)) throw new Error('sceneops_id already exists');
  if (input.parentSceneopsId && !objectIndex.has(input.parentSceneopsId)) {
    throw new Error('Placement parent does not exist');
  }
  assertFiniteVector(input.worldPosition, 'worldPosition');
  assertFiniteVector(input.dropRayOrigin, 'dropRayOrigin');
  assertUnitVector(input.dropRayDirection, 'dropRayDirection');
  assertFiniteVector(input.scale, 'scale');
  assertUnitVector(input.worldNormal, 'worldNormal');
  assertCameraPose(input.camera);
  if (!input.rationale.trim()) throw new Error('Placement rationale is required');

  const object: WorldObjectRecord = {
    sceneopsId: input.newSceneopsId,
    displayName: input.displayName,
    parentSceneopsId: input.parentSceneopsId,
    asset: structuredClone(input.asset),
    transform: {
      position: structuredClone(input.worldPosition),
      rotation: structuredClone(input.rotation),
      scale: structuredClone(input.scale),
    },
    collider: structuredClone(input.collider),
    spawnRadiusMeters: null,
    navigationNodeId: null,
    requirements: structuredClone(input.requirements),
  };
  validateWorldLevelDocument({ ...structuredClone(scene), objects: [...scene.objects, object] });

  return {
    schemaVersion: 1,
    mutationKind: 'world.scene-object.place',
    baseVersion: input.baseVersion,
    targetModule: 'world-composer',
    targetIntegration: input.targetIntegration,
    targetSceneId: scene.sceneId,
    targetObjectIds: [object.sceneopsId],
    previousValues: null,
    proposedValues: {
      object,
      dropEvidence: {
        worldPosition: structuredClone(input.worldPosition),
        surfaceNormal: structuredClone(input.worldNormal),
        rayOrigin: structuredClone(input.dropRayOrigin),
        rayDirection: structuredClone(input.dropRayDirection),
        camera: structuredClone(input.camera),
      },
    },
    rationale: input.rationale,
    expectedResult: `${input.displayName} is placed as a new traceable scene instance.`,
    impactScope: [`scene:${scene.sceneId}`, `scene-object:${object.sceneopsId}`],
    risk: 'medium',
    validationPlan: [
      'Run all world.level gates against the dry-run snapshot.',
      'Verify asset-version to scene-instance identity mapping.',
      'Capture a fixed-camera comparison after execution.',
    ],
    rollbackPlan: [
      `Remove scene instance ${object.sceneopsId} through the same typed adapter.`,
      `Restore scene version ${scene.sceneVersion}.`,
    ],
    approvalRoles: ['level-designer'],
    dryRunRequired: true,
    mode: 'planned',
  };
}

export async function submitPlacementChangeSet(
  plan: WorldMutationPlan<PlacementProposal>,
  gateway: ChangeSetGateway,
): Promise<ChangeSetHandle> {
  if (plan.mutationKind !== 'world.scene-object.place') throw new Error('Unexpected mutation kind');
  return gateway.create(plan);
}
