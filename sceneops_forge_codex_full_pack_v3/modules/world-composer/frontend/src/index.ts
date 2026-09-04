export { validateAnnotation, serializeAnnotation, restoreAnnotation } from './annotations.ts';
export {
  evaluateWorldCommandAvailability,
  worldCommandDefinitions,
  type WorldCommandAccessProjection,
  type WorldCommandAvailability,
  type WorldCommandDefinition,
} from './commands.ts';
export * from './contracts.ts';
export {
  buildWorldEditorScreen,
  type WorldEditorInput,
  type WorldEditorScreen,
  type WorldEditorStatus,
} from './editor-state.ts';
export {
  worldEditorDefinitions,
  type WorldEditorDefinition,
} from './editors/definitions.ts';
export {
  createFixedCameraCaptureRequest,
  restoreIssueContext,
  type FixedCameraCaptureRequest,
  type IssueRestorationPorts,
  type IssueRestorationResult,
  type WorldContextBinding,
  type WorldContextProjection,
  type WorldIssueContext,
} from './issue-restoration.ts';
export {
  validateLevel,
  type LevelGateId,
  type LevelGateIssue,
  type LevelGateReport,
  type LevelGateResult,
} from './level-gates.ts';
export { manifest, moduleContribution } from './manifest.ts';
export { worldLevelPolicyGate, worldLevelValidationJob, worldWorkflows } from './module-jobs.ts';
export {
  createAssetPlacementPlan,
  submitPlacementChangeSet,
  type AssetDragPlacementInput,
  type ChangeSetGateway,
  type ChangeSetHandle,
  type PlacementProposal,
  type WorldMutationKind,
  type WorldMutationPlan,
} from './placement.ts';
export {
  compilePlacementRecipe,
  type GrayboxRecipe,
  type ProceduralGridRecipe,
  type RecipeProposal,
  type WorldPlacementRecipe,
} from './recipes.ts';
export {
  createObjectSpatialContext,
  createSceneSpatialContext,
  restoreSurfaceAnchor,
  type SurfaceAnchorRestoration,
} from './spatial-context.ts';
export { pinWorldContext, resolveWorldContext } from './state/context.ts';
export {
  DeterministicMockWorldMutationAdapter,
  WorldAdapterError,
  type ApprovedWorldMutation,
  type WorldAdapterCapabilities,
  type WorldAdapterHealth,
  type WorldAdapterErrorCode,
  type WorldMutationAdapter,
  type WorldMutationPreview,
  type WorldMutationProgress,
  type WorldMutationResult,
  type WorldMutationValidation,
} from './world-mutation-adapter.ts';
export {
  indexSceneObjects,
  parseWorldLevelDocument,
  validateWorldLevelDocument,
} from './world-model.ts';
export {
  createWorldOverlayRegistry,
  type WorldOverlayContext,
  type WorldOverlayPayload,
} from './world-overlays.ts';
export {
  createWorldGraphUpdatePlan,
  type WorldGraphUpdateInput,
  type WorldGraphUpdateProposal,
} from './world-graph-plan.ts';
export {
  createVoiceDraftAnnotation,
  type VoiceDraftOutcome,
  type VoiceTranscriptSource,
} from './voice-draft.ts';

export const loadWorldWorkbench = () => import('./web/WorldWorkbench.tsx');
export type { WorldWorkbenchProps } from './web/WorldWorkbench.tsx';
export const loadWorldSession = () => import('./web/world-session.ts');
export type { WorldSession } from './web/world-session.ts';
