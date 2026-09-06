import { requestJson } from '@sceneops/api-client';
import type { components } from './generated/workspace-api';
export type Project = components['schemas']['Project'];
export type ModuleDocument = components['schemas']['ModuleDocument'];
export type ModuleId = ModuleDocument['module_id'];
export type FolderEntry = components['schemas']['FolderEntry'];
export type FolderListing = components['schemas']['FolderListing'];
export type FolderProject = components['schemas']['FolderProject'];
export const workspaceClient = {
  modules: () => requestJson<components['schemas']['ModuleList']>('/api/workspace/modules'),
  projects: () => requestJson<components['schemas']['ProjectList']>('/api/workspace/projects'),
  create: (body: components['schemas']['ProjectCreate']) => requestJson<Project>('/api/workspace/projects', { body }),
  document: (id: string, module: ModuleId) => requestJson<ModuleDocument>(`/api/workspace/projects/${encodeURIComponent(id)}/modules/${module}`),
  save: (id: string, module: ModuleId, body: components['schemas']['DocumentSave']) => requestJson<ModuleDocument>(`/api/workspace/projects/${encodeURIComponent(id)}/modules/${module}`, { method: 'PUT', body }),
  sample: (id: string, module: ModuleId, body: components['schemas']['SampleImport']) => requestJson<ModuleDocument>(`/api/workspace/projects/${encodeURIComponent(id)}/modules/${module}/sample`, { body }),
  folders: (path?: string) => requestJson<FolderListing>(`/api/workspace/folders${path ? `?path=${encodeURIComponent(path)}` : ''}`),
  folderProjects: () => requestJson<components['schemas']['FolderProjectList']>('/api/workspace/folder-projects'),
  folderProject: (id: string) => requestJson<FolderProject>(`/api/workspace/folder-projects/${encodeURIComponent(id)}`),
  createFolderProject: (body: components['schemas']['FolderProjectCreate']) => requestJson<FolderProject>('/api/workspace/folder-projects', { body }),
};
