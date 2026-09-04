import { type SceneOpsId } from './scene-object-index.ts';
import { type Vector3 } from './spatial.ts';

interface CameraPoseBase {
  readonly position: Vector3;
  readonly target: Vector3;
  readonly up: Vector3;
  readonly nearClipMeters: number;
  readonly farClipMeters: number;
  readonly coordinateSpace: 'world';
  readonly axisConvention: 'right-handed-y-up';
  readonly units: 'meters';
}

export interface PerspectiveCameraPose extends CameraPoseBase {
  readonly projection: 'perspective';
  readonly verticalFovRadians: number;
}

export interface OrthographicCameraPose extends CameraPoseBase {
  readonly projection: 'orthographic';
  readonly verticalSpanMeters: number;
}

export type CameraPose = PerspectiveCameraPose | OrthographicCameraPose;

export interface CameraStatePort {
  readCameraPose(): CameraPose;
  applyCameraPose(pose: CameraPose): void;
}

export interface CameraCaptureMetadata {
  readonly captureId: string;
  readonly sceneId: string;
  readonly sceneVersion: string;
  readonly capturedAt: string;
  readonly selectedSceneopsIds: readonly SceneOpsId[];
}

export interface CameraCapture extends CameraCaptureMetadata {
  readonly pose: CameraPose;
}

export interface CameraRestoreContext {
  readonly sceneId: string;
  readonly sceneVersion: string;
}

export type CameraStateErrorCode =
  | 'INVALID_CAMERA_POSE'
  | 'INVALID_CAPTURE_METADATA'
  | 'SCENE_MISMATCH'
  | 'SCENE_VERSION_MISMATCH'
  | 'DUPLICATE_VIEWPORT'
  | 'UNKNOWN_VIEWPORT'
  | 'INVALID_VIEWPORT_ID';

export class CameraStateError extends Error {
  readonly code: CameraStateErrorCode;

  constructor(code: CameraStateErrorCode, message: string) {
    super(message);
    this.name = 'CameraStateError';
    this.code = code;
  }
}

export function captureCameraState(
  port: CameraStatePort,
  metadata: CameraCaptureMetadata,
): CameraCapture {
  assertCaptureMetadata(metadata);
  const sourcePose = port.readCameraPose();
  assertCameraPose(sourcePose);
  const pose = cloneCameraPose(sourcePose);
  return Object.freeze({
    ...metadata,
    selectedSceneopsIds: Object.freeze([...metadata.selectedSceneopsIds]),
    pose,
  });
}

export function restoreCameraState(
  capture: CameraCapture,
  port: CameraStatePort,
  context: CameraRestoreContext,
): void {
  if (capture.sceneId !== context.sceneId) {
    throw new CameraStateError(
      'SCENE_MISMATCH',
      `Capture belongs to scene ${capture.sceneId}, not ${context.sceneId}.`,
    );
  }
  if (capture.sceneVersion !== context.sceneVersion) {
    throw new CameraStateError(
      'SCENE_VERSION_MISMATCH',
      `Capture belongs to scene version ${capture.sceneVersion}, not ${context.sceneVersion}.`,
    );
  }
  assertCameraPose(capture.pose);
  port.applyCameraPose(cloneCameraPose(capture.pose));
}

export class CameraComparisonSynchronizer {
  readonly #ports = new Map<string, CameraStatePort>();

  register(viewportId: string, port: CameraStatePort): () => void {
    assertIdentifier(viewportId, 'viewportId', 'INVALID_VIEWPORT_ID');
    if (this.#ports.has(viewportId)) {
      throw new CameraStateError(
        'DUPLICATE_VIEWPORT',
        `Viewport ${viewportId} is already registered for camera sync.`,
      );
    }
    this.#ports.set(viewportId, port);
    return () => {
      if (this.#ports.get(viewportId) === port) this.#ports.delete(viewportId);
    };
  }

  synchronizeFrom(sourceViewportId: string): readonly string[] {
    const source = this.#ports.get(sourceViewportId);
    if (!source) {
      throw new CameraStateError(
        'UNKNOWN_VIEWPORT',
        `Viewport ${sourceViewportId} is not registered for camera sync.`,
      );
    }
    const pose = cloneCameraPose(source.readCameraPose());
    assertCameraPose(pose);
    const synchronized: string[] = [];
    for (const [viewportId, port] of this.#ports) {
      if (viewportId === sourceViewportId) continue;
      port.applyCameraPose(cloneCameraPose(pose));
      synchronized.push(viewportId);
    }
    return Object.freeze(synchronized);
  }

  listViewportIds(): readonly string[] {
    return Object.freeze([...this.#ports.keys()]);
  }
}

export function cloneCameraPose(pose: CameraPose): CameraPose {
  const base = {
    position: cloneVector3(pose.position),
    target: cloneVector3(pose.target),
    up: cloneVector3(pose.up),
    nearClipMeters: pose.nearClipMeters,
    farClipMeters: pose.farClipMeters,
    coordinateSpace: pose.coordinateSpace,
    axisConvention: pose.axisConvention,
    units: pose.units,
  } as const;
  return pose.projection === 'perspective'
    ? Object.freeze({ ...base, projection: 'perspective', verticalFovRadians: pose.verticalFovRadians })
    : Object.freeze({ ...base, projection: 'orthographic', verticalSpanMeters: pose.verticalSpanMeters });
}

export function assertCameraPose(pose: CameraPose): void {
  if (
    pose.coordinateSpace !== 'world'
    || pose.axisConvention !== 'right-handed-y-up'
    || pose.units !== 'meters'
    || (pose.projection !== 'perspective' && pose.projection !== 'orthographic')
  ) {
    throw new CameraStateError(
      'INVALID_CAMERA_POSE',
      'Camera pose requires world, right-handed Y-up, meter coordinates and a known projection.',
    );
  }
  const vectors = [pose.position, pose.target, pose.up];
  if (vectors.some((vector) => vector.some((value) => !Number.isFinite(value)))) {
    throw new CameraStateError('INVALID_CAMERA_POSE', 'Camera vectors must be finite.');
  }
  if (
    !Number.isFinite(pose.nearClipMeters)
    || !Number.isFinite(pose.farClipMeters)
    || !(pose.nearClipMeters > 0)
    || !(pose.farClipMeters > pose.nearClipMeters)
  ) {
    throw new CameraStateError(
      'INVALID_CAMERA_POSE',
      'Camera clip distances require 0 < near < far.',
    );
  }
  const forward = subtract(pose.target, pose.position);
  if (length(forward) <= 1e-12 || length(pose.up) <= 1e-12) {
    throw new CameraStateError(
      'INVALID_CAMERA_POSE',
      'Camera position, target, and up must define non-zero directions.',
    );
  }
  if (length(cross(forward, pose.up)) <= 1e-12) {
    throw new CameraStateError(
      'INVALID_CAMERA_POSE',
      'Camera up cannot be parallel to the view direction.',
    );
  }
  if (
    pose.projection === 'perspective'
    && (
      !Number.isFinite(pose.verticalFovRadians)
      || !(pose.verticalFovRadians > 0)
      || !(pose.verticalFovRadians < Math.PI)
    )
  ) {
    throw new CameraStateError(
      'INVALID_CAMERA_POSE',
      'Perspective field of view must be between zero and pi radians.',
    );
  }
  if (
    pose.projection === 'orthographic'
    && (!Number.isFinite(pose.verticalSpanMeters) || !(pose.verticalSpanMeters > 0))
  ) {
    throw new CameraStateError(
      'INVALID_CAMERA_POSE',
      'Orthographic vertical span must be greater than zero.',
    );
  }
}

function assertCaptureMetadata(metadata: CameraCaptureMetadata): void {
  for (const [label, value] of [
    ['captureId', metadata.captureId],
    ['sceneId', metadata.sceneId],
    ['sceneVersion', metadata.sceneVersion],
    ['capturedAt', metadata.capturedAt],
  ] as const) {
    assertIdentifier(value, label);
  }
  if (
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(metadata.capturedAt)
    || Number.isNaN(Date.parse(metadata.capturedAt))
  ) {
    throw new CameraStateError(
      'INVALID_CAPTURE_METADATA',
      'capturedAt must be an ISO-8601 timestamp.',
    );
  }
  if (new Set(metadata.selectedSceneopsIds).size !== metadata.selectedSceneopsIds.length) {
    throw new CameraStateError(
      'INVALID_CAPTURE_METADATA',
      'selectedSceneopsIds must not contain duplicates.',
    );
  }
  for (const sceneopsId of metadata.selectedSceneopsIds) {
    assertIdentifier(sceneopsId, 'selected sceneops_id');
  }
}

function assertIdentifier(
  value: string,
  label: string,
  code: 'INVALID_CAPTURE_METADATA' | 'INVALID_VIEWPORT_ID' = 'INVALID_CAPTURE_METADATA',
): void {
  if (value.length === 0 || value.trim() !== value) {
    throw new CameraStateError(
      code,
      `${label} must be a non-empty, trimmed string.`,
    );
  }
}

function cloneVector3(vector: Vector3): Vector3 {
  return Object.freeze([vector[0], vector[1], vector[2]]);
}

function subtract(left: Vector3, right: Vector3): Vector3 {
  return [left[0] - right[0], left[1] - right[1], left[2] - right[2]];
}

function cross(left: Vector3, right: Vector3): Vector3 {
  return [
    left[1] * right[2] - left[2] * right[1],
    left[2] * right[0] - left[0] * right[2],
    left[0] * right[1] - left[1] * right[0],
  ];
}

function length(vector: Vector3): number {
  return Math.hypot(...vector);
}
