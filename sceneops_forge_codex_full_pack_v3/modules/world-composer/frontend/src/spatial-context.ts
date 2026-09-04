import {
  SceneObjectIndex,
  SceneTransformResolver,
  normalizeVector3,
  type Vector3,
} from '@sceneops/scene-viewer';
import {
  canonicalCoordinateSystem,
  type ObjectSpatialContext,
  type SceneSpatialContext,
  type SurfacePinDetails,
} from './contracts.ts';

export function createObjectSpatialContext(
  index: SceneObjectIndex,
  resolver: SceneTransformResolver,
  sceneopsId: string,
  localPosition: Vector3,
  localNormal: Vector3,
): ObjectSpatialContext {
  const object = index.require(sceneopsId);
  const normalizedLocal = normalizeVector3(localNormal);
  return {
    reference: {
      kind: 'object',
      object: { sceneopsId: object.sceneopsId, displayName: object.name },
    },
    localPosition: [...localPosition],
    worldPosition: resolver.localPointToWorld(sceneopsId, localPosition),
    localNormal: normalizedLocal,
    worldNormal: resolver.localNormalToWorld(sceneopsId, normalizedLocal),
    coordinateSystem: canonicalCoordinateSystem,
  };
}

export function createSceneSpatialContext(
  sceneId: string,
  worldPosition: Vector3,
  worldNormal: Vector3,
): SceneSpatialContext {
  if (!sceneId.trim()) throw new Error('sceneId is required');
  const normal = normalizeVector3(worldNormal);
  return {
    reference: { kind: 'scene', sceneId },
    localPosition: [...worldPosition],
    worldPosition: [...worldPosition],
    localNormal: normal,
    worldNormal: normal,
    coordinateSystem: canonicalCoordinateSystem,
  };
}

export interface SurfaceAnchorRestoration {
  status: 'restored' | 'stale';
  geometryVersion: string;
  capturedWorldPosition: Vector3;
  capturedWorldNormal: Vector3;
  currentWorldPosition?: Vector3;
  currentWorldNormal?: Vector3;
  reason?: string;
}

export function restoreSurfaceAnchor(
  spatial: ObjectSpatialContext,
  details: SurfacePinDetails,
  currentGeometryVersion: string,
  resolver: SceneTransformResolver,
): SurfaceAnchorRestoration {
  if (details.geometryVersion !== currentGeometryVersion) {
    return {
      status: 'stale',
      geometryVersion: currentGeometryVersion,
      capturedWorldPosition: [...spatial.worldPosition],
      capturedWorldNormal: [...spatial.worldNormal],
      reason: `Surface topology changed from ${details.geometryVersion} to ${currentGeometryVersion}; nearest-surface fallback is forbidden.`,
    };
  }
  const sceneopsId = spatial.reference.object.sceneopsId;
  return {
    status: 'restored',
    geometryVersion: currentGeometryVersion,
    capturedWorldPosition: [...spatial.worldPosition],
    capturedWorldNormal: [...spatial.worldNormal],
    currentWorldPosition: resolver.localPointToWorld(sceneopsId, spatial.localPosition),
    currentWorldNormal: resolver.localNormalToWorld(sceneopsId, spatial.localNormal),
  };
}
