import { assertCameraPose } from '@sceneops/scene-viewer';
import type {
  CameraPose,
  WorldExecutionMode,
  JsonValue,
  WorldLevelDocument,
} from './contracts.ts';
import { isWorldExecutionMode } from './execution.ts';
import { indexSceneObjects, validateWorldLevelDocument } from './world-model.ts';

export interface WorldIssueContext {
  issueId: string;
  projectId: string;
  sceneId: string;
  sceneVersion: string;
  targetSceneopsIds: string[];
  camera: CameraPose;
  pathId: string | null;
  evidenceIds: string[];
  gameStateVersion: string;
  gameState: Record<string, JsonValue>;
  buildId: string | null;
  playtestRunId: string | null;
  playtestStepId: string | null;
  mode: WorldExecutionMode;
}

export interface WorldContextProjection {
  projectId: string | null;
  sceneId: string | null;
  selectedSceneObjectIds: string[];
  activeIssueId: string | null;
  cameraPose?: CameraPose;
}

export type WorldContextBinding =
  | { mode: 'follow-global' }
  | { mode: 'pinned'; context: Partial<WorldContextProjection> };

export interface IssueRestorationPorts {
  restoreCamera(camera: CameraPose): void;
  selectObjects(sceneopsIds: string[]): void;
  showPath(pathId: string): void;
  hasEvidence(evidenceId: string): boolean;
  updateGlobalContext(context: WorldContextProjection): void;
}

export interface RestorationComponentResult {
  component: 'scene' | 'objects' | 'camera' | 'path' | 'evidence' | 'context';
  status: 'restored' | 'missing' | 'stale' | 'blocked';
  message: string;
}

export interface IssueRestorationResult {
  issueId: string;
  state: 'restored' | 'partial' | 'blocked';
  mode: WorldExecutionMode;
  components: RestorationComponentResult[];
}

function component(
  name: RestorationComponentResult['component'],
  status: RestorationComponentResult['status'],
  message: string,
): RestorationComponentResult {
  return { component: name, status, message };
}

export function restoreIssueContext(
  scene: WorldLevelDocument,
  issue: WorldIssueContext,
  binding: WorldContextBinding,
  ports: IssueRestorationPorts,
): IssueRestorationResult {
  validateWorldLevelDocument(scene);
  if (!issue.issueId || !issue.projectId || !issue.sceneId || !issue.sceneVersion) {
    throw new Error('Issue spatial identity is required');
  }
  if (new Set(issue.targetSceneopsIds).size !== issue.targetSceneopsIds.length) {
    throw new Error('Issue target IDs must be unique');
  }
  if (!issue.gameStateVersion || !isWorldExecutionMode(issue.mode)) {
    throw new Error('Issue game-state version and execution mode are required');
  }
  assertCameraPose(issue.camera);
  if (scene.sceneId !== issue.sceneId || scene.sceneVersion !== issue.sceneVersion) {
    return {
      issueId: issue.issueId,
      state: 'blocked',
      mode: 'blocked',
      components: [
        component(
          'scene',
          'stale',
          `Exact scene ${issue.sceneId}@${issue.sceneVersion} is required; latest-scene fallback is forbidden.`,
        ),
      ],
    };
  }

  const results: RestorationComponentResult[] = [
    component('scene', 'restored', `Restored ${scene.sceneId}@${scene.sceneVersion}.`),
  ];
  const objectIndex = indexSceneObjects(scene.objects);
  const foundIds = issue.targetSceneopsIds.filter((id) => objectIndex.has(id));
  const missingIds = issue.targetSceneopsIds.filter((id) => !objectIndex.has(id));
  ports.selectObjects(foundIds);
  results.push(
    component(
      'objects',
      missingIds.length === 0 ? 'restored' : 'missing',
      missingIds.length === 0
        ? `Selected ${foundIds.length} stable scene object(s).`
        : `Missing stable scene object(s): ${missingIds.join(', ')}.`,
    ),
  );

  ports.restoreCamera(structuredClone(issue.camera));
  results.push(component('camera', 'restored', 'Restored the captured camera without interpolation.'));

  if (issue.pathId === null) {
    results.push(component('path', 'missing', 'Issue has no path reference.'));
  } else if (scene.world.paths.some((path) => path.pathId === issue.pathId)) {
    ports.showPath(issue.pathId);
    results.push(component('path', 'restored', `Restored path ${issue.pathId}.`));
  } else {
    results.push(component('path', 'missing', `Path ${issue.pathId} is not present in this scene version.`));
  }

  const missingEvidence = issue.evidenceIds.filter((id) => !ports.hasEvidence(id));
  results.push(
    component(
      'evidence',
      missingEvidence.length === 0 ? 'restored' : 'missing',
      missingEvidence.length === 0
        ? `Resolved ${issue.evidenceIds.length} evidence reference(s).`
        : `Missing evidence: ${missingEvidence.join(', ')}.`,
    ),
  );

  if (binding.mode === 'follow-global') {
    ports.updateGlobalContext({
      projectId: issue.projectId,
      sceneId: issue.sceneId,
      selectedSceneObjectIds: foundIds,
      activeIssueId: issue.issueId,
      cameraPose: structuredClone(issue.camera),
    });
    results.push(component('context', 'restored', 'Updated follow-global context.'));
  } else {
    results.push(component('context', 'restored', 'Pinned context was intentionally left unchanged.'));
  }

  return {
    issueId: issue.issueId,
    state: results.every((entry) => entry.status === 'restored') ? 'restored' : 'partial',
    mode: scene.mode,
    components: results,
  };
}

export interface FixedCameraCaptureRequest {
  schemaVersion: 1;
  requestId: string;
  sceneId: string;
  sceneVersion: string;
  camera: CameraPose;
  widthPixels: number;
  heightPixels: number;
  overlayIds: string[];
  mode: 'planned';
}

export function createFixedCameraCaptureRequest(
  input: Omit<FixedCameraCaptureRequest, 'schemaVersion' | 'mode'>,
): FixedCameraCaptureRequest {
  if (!input.requestId || !input.sceneId || !input.sceneVersion) throw new Error('Capture identity is required');
  assertCameraPose(input.camera);
  if (!Number.isInteger(input.widthPixels) || !Number.isInteger(input.heightPixels)) {
    throw new Error('Capture dimensions must be integers');
  }
  if (input.widthPixels <= 0 || input.heightPixels <= 0) {
    throw new Error('Capture dimensions must be positive');
  }
  return { schemaVersion: 1, ...structuredClone(input), mode: 'planned' };
}
