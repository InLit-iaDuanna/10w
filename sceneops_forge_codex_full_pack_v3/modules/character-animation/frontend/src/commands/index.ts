import { z, type ZodType } from 'zod';
import type {
  CharacterInspectionRequest,
  CharacterInspectionResult,
  PreviewArtifact,
  PreviewCaptureRequest,
  RetargetPreviewRequest,
  RetargetPreviewResult,
  UnityCharacterMapping,
  UnityMappingExecutionRequest,
  UnityMappingProposalRequest,
  UnityMappingProposalResult,
  VersionComparisonRequest,
  VersionComparisonResult,
  VersionReviewRequest,
  VersionReviewResult,
} from '../api-types';
import type {
  CommandAvailability,
  CommandExecutionContext,
  CommandGuardContext,
  CharacterAnimationPostPath,
  WorkbenchCommandDefinition,
} from '../types';

const objectValue = z.object({}).loose();
const positiveTimeout = z.number().positive().optional();

function requestSchema<T>(shape: z.ZodRawShape): ZodType<T> {
  return z.object({ request_id: z.string().min(3), ...shape }).loose() as ZodType<T>;
}

function availability(
  requiredPermissions: string[],
  requiredIntegration?: string,
): (context: CommandGuardContext) => CommandAvailability {
  return (context) => {
    if (!context.moduleEnabled) return { available: false, code: 'MODULE_DISABLED', reason: '角色动画模块已禁用。' };
    if (!context.workbench.projectId) return { available: false, code: 'PROJECT_REQUIRED', reason: '请先选择项目。' };
    if (requiredPermissions.some((permission) => !context.permissions.has(permission))) {
      return { available: false, code: 'PERMISSION_DENIED', reason: '缺少所需角色动画权限。' };
    }
    if (requiredIntegration && !context.integrations.has(requiredIntegration)) {
      return { available: false, code: 'INTEGRATION_OFFLINE', reason: `${requiredIntegration} 集成当前离线。` };
    }
    return { available: true };
  };
}

function post<TRequest, TResult>(path: CharacterAnimationPostPath) {
  return (context: CommandExecutionContext, input: TRequest) => context.api.post<TRequest, TResult>(path, input);
}

export const inspectCharacterCommand: WorkbenchCommandDefinition<CharacterInspectionRequest, CharacterInspectionResult> = {
  id: 'character.inspect',
  title: '检查角色与动画',
  inputSchema: requestSchema({ bundle: objectValue, mode: z.enum(['live', 'cached', 'mock', 'planned', 'blocked']) }),
  requiredPermissions: ['character:read', 'animation:read'],
  canExecute: availability(['character:read', 'animation:read']),
  execute: post('/api/modules/character-animation/inspect'),
};

export const compareCharacterVersionCommand: WorkbenchCommandDefinition<VersionComparisonRequest, VersionComparisonResult> = {
  id: 'character.version.compare',
  title: '比较角色动画版本',
  inputSchema: requestSchema({ entity_type: z.enum(['rig', 'clip']), base: objectValue, proposed: objectValue }),
  requiredPermissions: ['character:read'],
  canExecute: availability(['character:read']),
  execute: post('/api/modules/character-animation/versions/compare'),
};

export const reviewCharacterVersionCommand: WorkbenchCommandDefinition<VersionReviewRequest, VersionReviewResult> = {
  id: 'character.version.review',
  title: '审批 Rig 或动画片段版本',
  inputSchema: requestSchema({
    entity_type: z.enum(['rig', 'clip']),
    entity_id: z.string().min(3),
    decision: z.enum(['approve', 'reject']),
    reviewer_id: z.string().min(3),
    reviewed_at: z.string().datetime({ offset: true }),
    comment: z.string().min(1),
  }),
  requiredPermissions: ['character:review'],
  canExecute: availability(['character:review']),
  execute: post('/api/modules/character-animation/versions/review'),
};

export const captureAnimationPreviewCommand: WorkbenchCommandDefinition<PreviewCaptureRequest, PreviewArtifact> = {
  id: 'animation.preview.capture',
  title: '捕获固定相机动画预览',
  inputSchema: requestSchema({
    timeout_seconds: positiveTimeout,
    character: objectValue,
    rig: objectValue,
    clip: objectValue,
    camera: objectValue,
    baseline_preview: objectValue.optional(),
  }),
  requiredPermissions: ['animation:read'],
  requiredIntegrations: ['character-preview'],
  canExecute: availability(['animation:read'], 'character-preview'),
  execute: post('/api/modules/character-animation/previews/capture'),
};

export const previewRetargetCommand: WorkbenchCommandDefinition<RetargetPreviewRequest, RetargetPreviewResult> = {
  id: 'animation.retarget.preview',
  title: '预览动画重定向',
  inputSchema: requestSchema({
    timeout_seconds: positiveTimeout,
    character: objectValue,
    source_rig: objectValue,
    target_rig: objectValue,
    source_clip: objectValue,
    profile: objectValue,
    camera: objectValue,
  }),
  requiredPermissions: ['animation:read'],
  requiredIntegrations: ['retargeting'],
  canExecute: availability(['animation:read'], 'retargeting'),
  execute: post('/api/modules/character-animation/previews/retarget'),
};

export const proposeUnityMappingCommand: WorkbenchCommandDefinition<UnityMappingProposalRequest, UnityMappingProposalResult> = {
  id: 'character.unity-mapping.propose',
  title: '提议 Unity 角色映射',
  inputSchema: requestSchema({
    bundle: objectValue,
    unity_prefab_id: z.string().min(3),
    unity_game_object_sceneops_id: z.string().min(3),
    unity_animator_controller_id: z.string().min(3),
    base_unity_version: z.string().min(1),
  }),
  requiredPermissions: ['character:write'],
  canExecute: availability(['character:write']),
  execute: post('/api/modules/character-animation/unity-mappings/propose'),
};

export const executeUnityMappingCommand: WorkbenchCommandDefinition<UnityMappingExecutionRequest, UnityCharacterMapping> = {
  id: 'character.unity-mapping.execute',
  title: '执行已批准的 Unity 角色映射',
  inputSchema: requestSchema({
    timeout_seconds: positiveTimeout,
    mapping: objectValue,
    changeset: objectValue,
  }),
  requiredPermissions: ['unity:write'],
  requiredIntegrations: ['unity'],
  canExecute: availability(['unity:write'], 'unity'),
  execute: post('/api/modules/character-animation/unity-mappings/execute'),
};

export const characterAnimationCommands = [
  inspectCharacterCommand,
  compareCharacterVersionCommand,
  reviewCharacterVersionCommand,
  captureAnimationPreviewCommand,
  previewRetargetCommand,
  proposeUnityMappingCommand,
  executeUnityMappingCommand,
];
