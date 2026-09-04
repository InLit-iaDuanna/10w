import { Matrix4, Quaternion, Vector3 as ThreeVector3 } from 'three';
import { createMatrix4, loadSceneObjectIndex, SceneSelectionModel, SceneTransformResolver } from '@sceneops/scene-viewer';
import type { ScenePreviewObject } from '@sceneops/scene-viewer/react';
import fixture from '../../../fixtures/remember-home/world.mock.json';
import { parseWorldLevelDocument } from '../world-model.ts';
import { createObjectSpatialContext } from '../spatial-context.ts';
import { validateAnnotation } from '../annotations.ts';
import type { CameraPose, JsonValue, WorldAnnotation } from '../contracts.ts';

export const defaultWorldCamera: CameraPose = {
  projection: 'perspective', position: [10, 9, 12], target: [0, 0, -0.5], up: [0, 1, 0],
  verticalFovRadians: Math.PI / 3, nearClipMeters: 0.1, farClipMeters: 200,
  coordinateSpace: 'world', axisConvention: 'right-handed-y-up', units: 'meters',
};

export function createWorldSession() {
  const scene = parseWorldLevelDocument(fixture);
  const index = loadSceneObjectIndex(scene.objects.map(object => {
    const { position, rotation, scale } = object.transform;
    const matrix = new Matrix4().compose(new ThreeVector3(...position), new Quaternion(rotation.x, rotation.y, rotation.z, rotation.w), new ThreeVector3(...scale));
    return { nodeKey: object.sceneopsId, name: object.displayName, extras: { sceneops_id: object.sceneopsId }, parentNodeKey: object.parentSceneopsId ?? undefined, assetId: object.asset?.assetId, localMatrix: createMatrix4(matrix.elements) };
  }));
  const selection = new SceneSelectionModel(index);
  selection.selectOnly('sobj_home_key');
  const resolver = new SceneTransformResolver(index);
  const objects: ScenePreviewObject[] = scene.objects.filter(object => object.parentSceneopsId !== null).map(object => ({
    sceneopsId: object.sceneopsId,
    size: object.collider?.sizeMeters ?? [0.5, 0.5, 0.5],
    color: object.sceneopsId === 'sobj_home_key' ? '#dba85c' : object.sceneopsId === 'sobj_home_entrance' ? '#748b8c' : '#79afb3',
  }));
  const paths = scene.world.paths.map(path => path.points.map(point => point.position));
  return { scene, index, selection, resolver, objects, paths };
}
export type WorldSession = ReturnType<typeof createWorldSession>;

export function createObjectNote(session: WorldSession, input: {
  sceneopsId: string; problem: string; intent: string; acceptance: string;
  camera: CameraPose; gameState: Record<string, JsonValue>; gameStateVersion: string;
}): WorldAnnotation {
  const annotation: WorldAnnotation = {
    schemaVersion: 1, annotationId: `ann_${crypto.randomUUID()}`, type: 'object-pin', status: 'draft',
    context: {
      projectId: session.scene.projectId, sceneId: session.scene.sceneId, sceneVersion: session.scene.sceneVersion,
      author: { type: 'user', id: 'usr_world_lab', displayName: '本地设计师' }, createdAt: new Date().toISOString(),
      spatial: createObjectSpatialContext(session.index, session.resolver, input.sceneopsId, [0, 0, 0], [0, 1, 0]),
      camera: structuredClone(input.camera), problem: input.problem, intent: input.intent, acceptance: [input.acceptance],
      constraints: ['保留现有稳定对象 ID'], evidence: [], gameState: structuredClone(input.gameState),
      gameStateVersion: input.gameStateVersion, mode: 'mock',
    }, details: { kind: 'object-pin' },
  };
  validateAnnotation(annotation);
  return annotation;
}
