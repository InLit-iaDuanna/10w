import { requestEventStream, requestJson } from '@sceneops/api-client';
import type { WorkbenchContext } from '@sceneops/core-ui';
import type { components } from '../generated/unified-ai-api.ts';

export type AISettings = components['schemas']['AISettings'];
export type AISettingsUpdate = components['schemas']['AISettingsUpdate'];
export type AIModels = components['schemas']['AIModels'];
export type AIConversation = components['schemas']['AIConversation'];
export type AIAdvice = components['schemas']['AIAdvice'];
export type AIChatStreamEvent = components['schemas']['AIChatStreamEvent'];
export type AIConnectionRequest = components['schemas']['AIConnectionRequest'];
export type AIConnectionResult = components['schemas']['AIConnectionResult'];
export type AIProviderModelsRequest = components['schemas']['AIProviderModelsRequest'];
export type AIProviderModels = components['schemas']['AIProviderModels'];
export type AIModuleDocument = Record<string, components['schemas']['JsonValue']>;
export const aiKeys = {
  models: ['unified-ai', 'models'] as const,
  settings: ['unified-ai', 'settings'] as const,
  conversation: (projectId: string | null) => ['unified-ai', 'conversation', projectId] as const,
};

export const readModels = (signal?: AbortSignal) => requestJson<AIModels>('/api/ai/models', { signal });
export const readSettings = (signal?: AbortSignal) => requestJson<AISettings>('/api/ai/settings', { signal });
export const saveSettings = (body: AISettingsUpdate) => requestJson<AISettings>('/api/ai/settings', { method: 'PUT', body });
export const readProviderModels = (body: AIProviderModelsRequest, signal: AbortSignal) =>
  requestJson<AIProviderModels>('/api/ai/provider/models', { body, signal });
export const checkProvider = (body: AIConnectionRequest, signal: AbortSignal) =>
  requestJson<AIConnectionResult>('/api/ai/provider/check', { body, signal });
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
  return requestJson<AIConversation>('/api/ai/chat', { body: chatBody(message, context, document), signal });
}

function chatBody(message: string, context: WorkbenchContext,
  document?: { moduleId: string; payload: AIModuleDocument }): components['schemas']['AIChatRequest'] {
  return {
    project_id: context.projectId, message, context: { ...selectedContext(context),
      ...(document ? { module_id: document.moduleId, module_document: document.payload } : {}) },
  };
}

export async function sendChatStream(message: string, context: WorkbenchContext,
  signal: AbortSignal, onEvent: (event: AIChatStreamEvent) => void,
  document?: { moduleId: string; payload: AIModuleDocument }): Promise<AIConversation> {
  let completed: AIConversation | undefined;
  await requestEventStream<AIChatStreamEvent>('/api/ai/chat/stream',
    chatBody(message, context, document), (event) => {
      if (event.type === 'error') throw new Error(event.text ?? '实时回复失败，请重试。');
      onEvent(event);
      if (event.type === 'complete' && event.conversation) completed = event.conversation;
    }, signal);
  if (!completed) throw new Error('实时回复结束，但没有收到已保存的完整对话。');
  return completed;
}

export function requestAdvice(prompt: string, moduleId: string, context: WorkbenchContext, signal: AbortSignal,
  moduleDocument?: AIModuleDocument) {
  const body: components['schemas']['AIAdviceRequest'] = {
    project_id: context.projectId, module_id: moduleId, prompt, context: { ...selectedContext(context),
      ...(moduleDocument ? { module_document: moduleDocument } : {}) },
  };
  return requestJson<AIAdvice>('/api/ai/advice', { body, signal });
}
