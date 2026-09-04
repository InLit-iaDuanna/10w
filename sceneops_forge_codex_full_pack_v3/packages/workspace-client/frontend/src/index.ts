import { requestJson } from '@sceneops/api-client';
import type { components } from './generated/workspace-api';
export type Project = components['schemas']['Project'];
export type ModuleDocument = components['schemas']['ModuleDocument'];
export type ModuleId = ModuleDocument['module_id'];
export const workspaceClient = {
  modules: () => requestJson<components['schemas']['ModuleList']>('/api/workspace/modules'),
  projects: () => requestJson<components['schemas']['ProjectList']>('/api/workspace/projects'),
  create: (body: components['schemas']['ProjectCreate']) => requestJson<Project>('/api/workspace/projects', { body }),
  document: (id: string, module: ModuleId) => requestJson<ModuleDocument>(`/api/workspace/projects/${encodeURIComponent(id)}/modules/${module}`),
  save: (id: string, module: ModuleId, body: components['schemas']['DocumentSave']) => requestJson<ModuleDocument>(`/api/workspace/projects/${encodeURIComponent(id)}/modules/${module}`, { method: 'PUT', body }),
  sample: (id: string, module: ModuleId, body: components['schemas']['SampleImport']) => requestJson<ModuleDocument>(`/api/workspace/projects/${encodeURIComponent(id)}/modules/${module}/sample`, { body }),
};
