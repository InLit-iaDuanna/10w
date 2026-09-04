import { readFileSync } from 'node:fs';

import { HOME_ISSUE_CAMERA } from '@sceneops/scene-viewer/fixtures';
import type {
  AnnotationDetails,
  SpatialContext,
  WorldAnnotation,
  WorldLevelDocument,
} from '../contracts.ts';

export const moduleRootUrl = new URL('../../../', import.meta.url);

export function readJson<T>(relativePath: string): T {
  return JSON.parse(readFileSync(new URL(relativePath, moduleRootUrl), 'utf8')) as T;
}

export function readWorld(relativePath: string): WorldLevelDocument {
  return readJson<WorldLevelDocument>(relativePath);
}

export function clone<T>(value: T): T {
  return structuredClone(value);
}

export function objectSpatial(sceneopsId = 'sobj_key_instance'): SpatialContext {
  return {
    reference: { kind: 'object', object: { sceneopsId, displayName: 'Front Door Key' } },
    localPosition: [0, 0.1, 0],
    worldPosition: [2, 0.9, 3],
    localNormal: [0, 1, 0],
    worldNormal: [0, 1, 0],
    coordinateSystem: { units: 'meters', handedness: 'right', upAxis: 'Y', forwardAxis: '-Z' },
  };
}

export function annotation(
  details: AnnotationDetails,
  spatial: SpatialContext = objectSpatial(),
): WorldAnnotation {
  return {
    schemaVersion: 1,
    annotationId: `ann_${details.kind}`,
    type: details.kind,
    status: details.kind === 'voice-draft' ? 'draft' : 'open',
    context: {
      projectId: 'prj_find_my_way_home',
      sceneId: 'scene_remember_home_hall',
      sceneVersion: 'scene-version-0007',
      author: { type: 'user', id: 'usr_level_designer', displayName: '关卡设计师' },
      createdAt: '2026-09-04T00:00:00Z',
      spatial,
      camera: HOME_ISSUE_CAMERA,
      problem: 'The target is difficult to read from the route.',
      intent: 'Make the intended interaction spatially unambiguous.',
      constraints: ['Keep the existing route width.'],
      acceptance: ['The target is visible before the player enters the interaction region.'],
      evidence: [
        {
          evidenceId: 'evidence_mock_capture',
          artifactId: 'artifact_mock_capture',
          mediaType: 'image',
          description: 'Deterministic mock viewport capture metadata.',
          mode: 'mock',
        },
      ],
      gameStateVersion: 'game-state-v1',
      gameState: { quest: 'find_key', hasKey: false },
      mode: 'mock',
    },
    details,
  };
}
