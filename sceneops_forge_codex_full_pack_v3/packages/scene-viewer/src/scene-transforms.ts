import { type SceneObjectIndex, type SceneOpsId } from './scene-object-index.ts';
import {
  IDENTITY_MATRIX4,
  invertMatrix4,
  multiplyMatrix4,
  normalizeVector3,
  transformNormal,
  transformPoint,
  type Matrix4,
  type Vector3,
} from './spatial.ts';

export class SceneTransformResolver {
  readonly #index: SceneObjectIndex;

  constructor(index: SceneObjectIndex) {
    this.#index = index;
  }

  worldMatrix(sceneopsId: SceneOpsId): Matrix4 {
    const lineage: Matrix4[] = [];
    const visited = new Set<SceneOpsId>();
    let currentId: SceneOpsId | null = sceneopsId;

    while (currentId !== null) {
      if (visited.has(currentId)) {
        throw new SceneTransformError(
          'CYCLIC_HIERARCHY',
          `Scene hierarchy contains a cycle at ${currentId}.`,
        );
      }
      visited.add(currentId);
      const current = this.#index.require(currentId);
      lineage.push(current.localMatrix);
      currentId = current.parentSceneopsId;
    }

    let world = IDENTITY_MATRIX4;
    for (let index = lineage.length - 1; index >= 0; index -= 1) {
      world = multiplyMatrix4(world, lineage[index]!);
    }
    return world;
  }

  localPointToWorld(sceneopsId: SceneOpsId, point: Vector3): Vector3 {
    return transformPoint(this.worldMatrix(sceneopsId), point);
  }

  worldPointToLocal(sceneopsId: SceneOpsId, point: Vector3): Vector3 {
    return transformPoint(invertMatrix4(this.worldMatrix(sceneopsId)), point);
  }

  localNormalToWorld(sceneopsId: SceneOpsId, normal: Vector3): Vector3 {
    return transformNormal(this.worldMatrix(sceneopsId), normal);
  }

  worldNormalToLocal(sceneopsId: SceneOpsId, normal: Vector3): Vector3 {
    const world = this.worldMatrix(sceneopsId);
    const [x, y, z] = normal;
    return normalizeVector3([
      world[0]! * x + world[1]! * y + world[2]! * z,
      world[4]! * x + world[5]! * y + world[6]! * z,
      world[8]! * x + world[9]! * y + world[10]! * z,
    ]);
  }
}

export class SceneTransformError extends Error {
  readonly code: 'CYCLIC_HIERARCHY';

  constructor(code: 'CYCLIC_HIERARCHY', message: string) {
    super(message);
    this.name = 'SceneTransformError';
    this.code = code;
  }
}
