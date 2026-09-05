import { requestJson } from '@sceneops/api-client';
import type { WorkbenchContext } from '@sceneops/core-ui';
import type { components } from '../generated/unified-ai-api.ts';

export type AISettings = components['schemas']['AISettings'];
export type AISettingsUpdate = components['schemas']['AISettingsUpdate'];
export type AIModels = components['schemas']['AIModels'];
export type AIConversation = components['schemas']['AIConversation'];
export type AIAdvice = components['schemas']['AIAdvice'];
export type AIModuleDocument = Record<string, components['schemas']['JsonValue']>;
export const aiKeys = {
  models: ['unified-ai', 'models'] as const,
  settings: ['unified-ai', 'settings'] as const,
  conversation: (projectId: string | null) => ['unified-ai', 'conversation', projectId] as const,
};

export const readModels = (signal?: AbortSignal) => requestJson<AIModels>('/api/ai/models', { signal });
export const readSettings = (signal?: AbortSignal) => requestJson<AISettings>('/api/ai/settings', { signal });
export const saveSettings = (body: AISettingsUpdate) => requestJson<AISettings>('/api/ai/settings', { method: 'PUT', body });
export const readConversation = (projectId: string | null, signal?: AbortSignal) =>
  requestJson<AIConversation>(`/api/ai/conversation${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''}`, { signal });

function selectedContext(context: WorkbenchContext) {
  return {
    project_id: context.projectId, branch_id: context.branchId, scene_id: context.sceneId,
    selected_scene_object_ids: context.selectedSceneObjectIds, selected_asset_ids: context.selectedAssetIds,
    feature_id: context.activeFeatureId, task_id: context.activeTaskId,
    changeset_id: context.activeChangeSetId, render_job_id: context.activeRenderJobId,
    build_id: context.activeBuildId, playtest_run_id: context.activePlaytestRunId, issue_id: context.activeIssueId,
  };
}

export function sendChat(message: string, context: WorkbenchContext, signal: AbortSignal,
  document?: { moduleId: string; payload: AIModuleDocument }) {
  const body: components['schemas']['AIChatRequest'] = {
    project_id: context.projectId, message, context: { ...selectedContext(context),
      ...(document ? { module_id: document.moduleId, module_document: document.payload } : {}) },
  };
  return requestJson<AIConversation>('/api/ai/chat', { body, signal });
}

export function requestAdvice(prompt: string, moduleId: string, context: WorkbenchContext, signal: AbortSignal,
  moduleDocument?: AIModuleDocument) {
  const body: components['schemas']['AIAdviceRequest'] = {
    project_id: context.projectId, module_id: moduleId, prompt, context: { ...selectedContext(context),
      ...(moduleDocument ? { module_document: moduleDocument } : {}) },
  };
  return requestJson<AIAdvice>('/api/ai/advice', { body, signal });
}
