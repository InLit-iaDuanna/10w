export {
  CameraComparisonSynchronizer,
  CameraStateError,
  assertCameraPose,
  captureCameraState,
  cloneCameraPose,
  restoreCameraState,
  type CameraCapture,
  type CameraCaptureMetadata,
  type CameraPose,
  type CameraRestoreContext,
  type CameraStatePort,
  type OrthographicCameraPose,
  type PerspectiveCameraPose,
} from './camera.ts';
export {
  SceneOverlayError,
  SceneOverlayRegistry,
  type ResolvedSceneOverlay,
  type SceneOverlayAvailability,
  type SceneOverlayDefinition,
  type SceneOverlayLayer,
} from './overlay-registry.ts';
export {
  ResourceCacheError,
  SharedResourceCache,
  type ResourceCacheEntrySnapshot,
  type ResourceCacheEntryState,
  type ResourceLease,
} from './resource-cache.ts';
export {
  SceneIdentityError,
  SceneObjectIndex,
  loadSceneObjectIndex,
  type SceneIdentityErrorCode,
  type SceneNodeDescriptor,
  type SceneObjectCopyRequest,
  type SceneObjectRecord,
  type SceneOpsId,
} from './scene-object-index.ts';
export { SceneTransformError, SceneTransformResolver } from './scene-transforms.ts';
export {
  SceneSelectionError,
  SceneSelectionModel,
  type SceneSelectionSnapshot,
  type SceneSelectionState,
  type SelectionBindingMode,
} from './selection.ts';
export {
  IDENTITY_MATRIX4,
  SpatialMathError,
  cloneMatrix4,
  createMatrix4,
  invertMatrix4,
  multiplyMatrix4,
  normalizeVector3,
  transformDirection,
  transformNormal,
  transformPoint,
  type Matrix4,
  type Vector3,
} from './spatial.ts';
export {
  ContinuousViewportBudget,
  ViewportLifecycleController,
  ViewportLifecycleError,
  type ViewportLifecycleSnapshot,
  type ViewportPixelSize,
  type ViewportRenderMode,
  type ViewportRuntimePort,
} from './viewport-lifecycle.ts';
