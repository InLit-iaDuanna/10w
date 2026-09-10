import { requestJson } from '@sceneops/api-client';
import type { components } from './api.generated';

export type ExportTask = components['schemas']['ExportTask'];
export type ExportPlatform = ExportTask['platforms'][number]['platform'];
export type ExportSettings = ExportTask['settings'];
const root = (projectId: string) => `/api/projects/${encodeURIComponent(projectId)}/exports`;
const taskPath = (projectId: string, taskId: string) => `${root(projectId)}/${encodeURIComponent(taskId)}`;
export const exportKeys = {
  list: (projectId: string) => ['project-exports', projectId] as const,
  task: (projectId: string, taskId: string) => ['project-export', projectId, taskId] as const,
};
export const exportApi = {
  list: (projectId: string) => requestJson<ExportTask[]>(root(projectId), { projectId }),
  get: (projectId: string, taskId: string) => requestJson<ExportTask>(taskPath(projectId, taskId), { projectId }),
  create: (projectId: string, body: components['schemas']['CreateExportRequest']) => requestJson<ExportTask>(root(projectId), { projectId, body }),
  message: (projectId: string, taskId: string, body: components['schemas']['ExportMessageRequest']) => requestJson<ExportTask>(`${taskPath(projectId, taskId)}/messages`, { projectId, body }),
  cancelAgent: (projectId: string, taskId: string) => requestJson<ExportTask>(`${taskPath(projectId, taskId)}/agent/cancel`, { projectId, body: {} }),
  consent: (projectId: string, taskId: string, body: components['schemas']['ExportConsentRequest']) => requestJson<ExportTask>(`${taskPath(projectId, taskId)}/settings`, { projectId, body }),
  refreshSource: (projectId: string, taskId: string) => requestJson<ExportTask>(`${taskPath(projectId, taskId)}/refresh-source`, { projectId, body: {} }),
  platformAction: (projectId: string, taskId: string, platform: ExportPlatform, action: 'continue' | 'cancel') => requestJson<ExportTask>(`${taskPath(projectId, taskId)}/platforms/${platform}/${action}`, { projectId, body: {} }),
  verify: (projectId: string, taskId: string, platform: ExportPlatform, body: components['schemas']['ExportVerificationRequest']) => requestJson<ExportTask>(`${taskPath(projectId, taskId)}/platforms/${platform}/verification`, { projectId, body }),
  events: (projectId: string, taskId: string) => `${taskPath(projectId, taskId)}/events`,
};
