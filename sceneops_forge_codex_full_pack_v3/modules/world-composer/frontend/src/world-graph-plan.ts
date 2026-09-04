import type { WorldGraph, WorldLevelDocument } from './contracts.ts';
import type { WorldMutationPlan } from './placement.ts';
import { validateWorldLevelDocument } from './world-model.ts';

export interface WorldGraphUpdateInput {
  baseVersion: string;
  proposedWorld: WorldGraph;
  rationale: string;
  targetIntegration: WorldMutationPlan<unknown>['targetIntegration'];
}

export interface WorldGraphUpdateProposal {
  world: WorldGraph;
}

function referencedObjectIds(world: WorldGraph): string[] {
  const ids = new Set<string>();
  world.zones.forEach((zone) => zone.objectIds.forEach((id) => ids.add(id)));
  world.interactionRegions.forEach((region) =>
    region.relatedSceneopsIds.forEach((id) => ids.add(id)),
  );
  world.relations.forEach((relation) => {
    ids.add(relation.sourceSceneopsId);
    ids.add(relation.targetSceneopsId);
  });
  world.lightingTargets.forEach((target) => ids.add(target.sceneopsId));
  return [...ids].sort();
}

export function createWorldGraphUpdatePlan(
  scene: WorldLevelDocument,
  input: WorldGraphUpdateInput,
): WorldMutationPlan<WorldGraphUpdateProposal> {
  validateWorldLevelDocument(scene);
  if (input.baseVersion !== scene.sceneVersion) throw new Error('STALE_SCENE_VERSION');
  if (!input.rationale.trim()) throw new Error('World graph rationale is required');
  const proposedScene: WorldLevelDocument = {
    ...structuredClone(scene),
    world: structuredClone(input.proposedWorld),
  };
  validateWorldLevelDocument(proposedScene);
  const targetObjectIds = referencedObjectIds(input.proposedWorld);
  return {
    schemaVersion: 1,
    mutationKind: 'world.graph.update',
    baseVersion: scene.sceneVersion,
    targetModule: 'world-composer',
    targetIntegration: input.targetIntegration,
    targetSceneId: scene.sceneId,
    targetObjectIds,
    previousValues: { world: structuredClone(scene.world) },
    proposedValues: { world: structuredClone(input.proposedWorld) },
    rationale: input.rationale,
    expectedResult: 'Update world zones, regions, paths, relations, navigation, and lighting targets as reviewed.',
    impactScope: [`scene:${scene.sceneId}`, ...targetObjectIds.map((id) => `scene-object:${id}`)],
    risk: 'high',
    validationPlan: ['Dry-run the graph update.', 'Run all six world.level gates.', 'Review fixed-camera evidence.'],
    rollbackPlan: [`Restore the prior world graph from scene version ${scene.sceneVersion}.`],
    approvalRoles: ['level-designer', 'project-owner'],
    dryRunRequired: true,
    mode: 'planned',
  };
}
