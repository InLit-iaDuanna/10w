import {
  canonicalCoordinateSystem,
  type AssetVersionRef,
  type CanonicalCoordinateSystem,
  type SceneObjectRequirements,
  type Transform,
  type Vector3,
  type WorldLevelDocument,
  type WorldObjectRecord,
} from './contracts.ts';
import type { WorldMutationPlan } from './placement.ts';
import { indexSceneObjects, validateWorldLevelDocument } from './world-model.ts';

interface RecipeBase {
  schemaVersion: 1;
  recipeId: string;
  recipeVersion: string;
  seed: string;
  constraints: string[];
  coordinateSystem: CanonicalCoordinateSystem;
}

export interface GrayboxPiece {
  sceneopsId: string;
  displayName: string;
  parentSceneopsId: string | null;
  transform: Transform;
  collider: NonNullable<WorldObjectRecord['collider']>;
  requirements: SceneObjectRequirements;
}

export interface GrayboxRecipe extends RecipeBase {
  kind: 'graybox-explicit-v1';
  pieces: GrayboxPiece[];
}

export interface ProceduralGridRecipe extends RecipeBase {
  kind: 'procedural-grid-v1';
  asset: AssetVersionRef;
  instanceSceneopsIds: string[];
  namePrefix: string;
  parentSceneopsId: string | null;
  origin: Vector3;
  columns: number;
  rows: number;
  columnSpacingMeters: number;
  rowSpacingMeters: number;
  rotation: Transform['rotation'];
  scale: Vector3;
  requirements: SceneObjectRequirements;
}

export type WorldPlacementRecipe = GrayboxRecipe | ProceduralGridRecipe;

export interface RecipeProposal {
  recipe: WorldPlacementRecipe;
  objects: WorldObjectRecord[];
}

function finiteVector(value: Vector3): boolean {
  return value.length === 3 && value.every(Number.isFinite);
}

function assertRecipeBase(recipe: WorldPlacementRecipe): void {
  if (!recipe.recipeId || !recipe.recipeVersion || !recipe.seed) {
    throw new Error('Recipe ID, version, and seed are required');
  }
  if (recipe.constraints.length === 0 || recipe.constraints.some((item) => !item.trim())) {
    throw new Error('At least one explicit recipe constraint is required');
  }
  if (
    recipe.coordinateSystem.units !== canonicalCoordinateSystem.units ||
    recipe.coordinateSystem.handedness !== canonicalCoordinateSystem.handedness ||
    recipe.coordinateSystem.upAxis !== canonicalCoordinateSystem.upAxis ||
    recipe.coordinateSystem.forwardAxis !== canonicalCoordinateSystem.forwardAxis
  ) {
    throw new Error('Recipe must declare the canonical coordinate system');
  }
}

function grayboxObjects(recipe: GrayboxRecipe): WorldObjectRecord[] {
  if (recipe.pieces.length === 0) throw new Error('Graybox recipe must contain a piece');
  return recipe.pieces.map((piece) => ({
    sceneopsId: piece.sceneopsId,
    displayName: piece.displayName,
    parentSceneopsId: piece.parentSceneopsId,
    transform: structuredClone(piece.transform),
    collider: structuredClone(piece.collider),
    spawnRadiusMeters: null,
    navigationNodeId: null,
    requirements: structuredClone(piece.requirements),
  }));
}

function gridObjects(recipe: ProceduralGridRecipe): WorldObjectRecord[] {
  if (!Number.isInteger(recipe.columns) || !Number.isInteger(recipe.rows)) {
    throw new Error('Grid dimensions must be integers');
  }
  if (recipe.columns <= 0 || recipe.rows <= 0) throw new Error('Grid dimensions must be positive');
  if (!Number.isFinite(recipe.columnSpacingMeters) || !Number.isFinite(recipe.rowSpacingMeters)) {
    throw new Error('Grid spacing must be finite');
  }
  if (recipe.columnSpacingMeters <= 0 || recipe.rowSpacingMeters <= 0) {
    throw new Error('Grid spacing must be positive');
  }
  if (!finiteVector(recipe.origin) || !finiteVector(recipe.scale)) throw new Error('Grid vectors are invalid');
  const count = recipe.columns * recipe.rows;
  if (recipe.instanceSceneopsIds.length !== count) {
    throw new Error(`Grid requires exactly ${count} core-issued sceneops_id values`);
  }
  return recipe.instanceSceneopsIds.map((sceneopsId, index) => {
    const column = index % recipe.columns;
    const row = Math.floor(index / recipe.columns);
    return {
      sceneopsId,
      displayName: `${recipe.namePrefix}_${index + 1}`,
      parentSceneopsId: recipe.parentSceneopsId,
      asset: structuredClone(recipe.asset),
      transform: {
        position: [
          recipe.origin[0] + column * recipe.columnSpacingMeters,
          recipe.origin[1],
          recipe.origin[2] + row * recipe.rowSpacingMeters,
        ],
        rotation: structuredClone(recipe.rotation),
        scale: structuredClone(recipe.scale),
      },
      collider: null,
      spawnRadiusMeters: null,
      navigationNodeId: null,
      requirements: structuredClone(recipe.requirements),
    };
  });
}

export function compilePlacementRecipe(
  scene: WorldLevelDocument,
  recipe: WorldPlacementRecipe,
  targetIntegration: WorldMutationPlan<unknown>['targetIntegration'],
): WorldMutationPlan<RecipeProposal> {
  validateWorldLevelDocument(scene);
  assertRecipeBase(recipe);
  const objects = recipe.kind === 'graybox-explicit-v1' ? grayboxObjects(recipe) : gridObjects(recipe);
  const existing = indexSceneObjects(scene.objects);
  const proposed = indexSceneObjects(objects);
  for (const object of proposed.values()) {
    if (existing.has(object.sceneopsId)) throw new Error(`sceneops_id already exists: ${object.sceneopsId}`);
    if (object.parentSceneopsId && !existing.has(object.parentSceneopsId) && !proposed.has(object.parentSceneopsId)) {
      throw new Error(`Recipe parent does not exist: ${object.parentSceneopsId}`);
    }
    if (object.asset?.assetId === object.sceneopsId) {
      throw new Error('Asset identity cannot be reused as scene instance identity');
    }
  }
  const mutationKind =
    recipe.kind === 'graybox-explicit-v1'
      ? 'world.graybox.apply'
      : 'world.procedural-placement.apply';
  return {
    schemaVersion: 1,
    mutationKind,
    baseVersion: scene.sceneVersion,
    targetModule: 'world-composer',
    targetIntegration,
    targetSceneId: scene.sceneId,
    targetObjectIds: objects.map((object) => object.sceneopsId),
    previousValues: null,
    proposedValues: { recipe: structuredClone(recipe), objects },
    rationale: `Apply reproducible recipe ${recipe.recipeId}@${recipe.recipeVersion}.`,
    expectedResult: `Create ${objects.length} traceable scene object(s).`,
    impactScope: [`scene:${scene.sceneId}`, ...objects.map((object) => `scene-object:${object.sceneopsId}`)],
    risk: 'high',
    validationPlan: ['Dry-run the recipe.', 'Run all world.level gates.', 'Review a fixed-camera comparison.'],
    rollbackPlan: [
      `Remove only the ${objects.length} instances created by this ChangeSet.`,
      `Restore scene version ${scene.sceneVersion}.`,
    ],
    approvalRoles: ['level-designer', 'project-owner'],
    dryRunRequired: true,
    mode: 'planned',
  };
}
