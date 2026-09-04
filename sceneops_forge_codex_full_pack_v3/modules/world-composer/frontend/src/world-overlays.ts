import { SceneOverlayRegistry } from '@sceneops/scene-viewer';
import type { WorldExecutionMode, WorldLevelDocument } from './contracts.ts';

export interface WorldOverlayContext {
  scene: WorldLevelDocument;
  renderBuffers: Partial<Record<'depth' | 'normals' | 'masks', string>>;
  heatmapArtifactId: string | null;
}

export interface WorldOverlayPayload {
  overlayId: string;
  mode: WorldExecutionMode;
  color: string;
  data: unknown;
}

function payload(
  context: WorldOverlayContext,
  overlayId: string,
  color: string,
  data: unknown,
): WorldOverlayPayload {
  return { overlayId, mode: context.scene.mode, color, data: structuredClone(data) };
}

export function createWorldOverlayRegistry(): SceneOverlayRegistry<WorldOverlayContext, WorldOverlayPayload> {
  const registry = new SceneOverlayRegistry<WorldOverlayContext, WorldOverlayPayload>();
  registry.register({
    id: 'scene.object-ids',
    label: 'Object IDs',
    layer: 'metadata',
    order: 10,
    isAvailable: () => true,
    createPayload: (context) =>
      payload(
        context,
        'scene.object-ids',
        '#58c8c5',
        context.scene.objects.map((object) => ({ sceneopsId: object.sceneopsId, label: object.displayName })),
      ),
  });
  registry.register({
    id: 'scene.colliders',
    label: 'Colliders',
    layer: 'geometry',
    order: 20,
    isAvailable: (context) => context.scene.gateInputs.colliders.state === 'available',
    createPayload: (context) =>
      payload(
        context,
        'scene.colliders',
        '#f2c14e',
        context.scene.objects.flatMap((object) =>
          object.collider ? [{ sceneopsId: object.sceneopsId, collider: object.collider }] : [],
        ),
      ),
  });
  registry.register({
    id: 'scene.navmesh',
    label: 'NavMesh',
    layer: 'geometry',
    order: 30,
    isAvailable: (context) => context.scene.gateInputs.navigation.state === 'available',
    createPayload: (context) => payload(context, 'scene.navmesh', '#58c8c5', context.scene.world.navigation),
  });
  registry.register({
    id: 'scene.paths',
    label: 'Paths',
    layer: 'geometry',
    order: 40,
    isAvailable: (context) => context.scene.gateInputs.navigation.state === 'available',
    createPayload: (context) => payload(context, 'scene.paths', '#eca85b', context.scene.world.paths),
  });
  for (const [id, label, order] of [
    ['depth', 'Depth', 50],
    ['normals', 'Normals', 60],
    ['masks', 'Masks', 70],
  ] as const) {
    registry.register({
      id: `scene.${id}`,
      label,
      layer: 'screen-space',
      order,
      isAvailable: (context) => Boolean(context.renderBuffers[id]),
      createPayload: (context) =>
        payload(context, `scene.${id}`, '#a58bfa', { bufferId: context.renderBuffers[id] ?? null }),
    });
  }
  registry.register({
    id: 'scene.heatmaps',
    label: 'Heatmaps',
    layer: 'screen-space',
    order: 80,
    isAvailable: (context) => context.heatmapArtifactId !== null,
    createPayload: (context) =>
      payload(context, 'scene.heatmaps', '#f06d6d', { artifactId: context.heatmapArtifactId }),
  });
  return registry;
}
