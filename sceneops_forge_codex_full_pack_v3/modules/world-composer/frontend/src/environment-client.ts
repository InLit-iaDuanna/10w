import { requestJson } from '@sceneops/api-client';
import type { components } from './generated/environment-api.ts';

export type EnvironmentScene = components['schemas']['EnvironmentScene'];
export type EnvironmentObject = components['schemas']['EnvironmentObject'];
export type EnvironmentTransform = components['schemas']['EnvironmentTransform'];
export type ProjectAssetEntry = components['schemas']['ProjectAssetEntry'];
export type AiBuildResult = components['schemas']['AiBuildResult'];
export type SharedProjectMemory = components['schemas']['SharedProjectMemory'];

export const environmentSceneKey = (projectId: string) => ['environment-scene', projectId] as const;
export const environmentAssetsKey = (projectId: string) => ['project-assets', projectId] as const;
export const environmentAssetUrl = (sourceAssetId: string, version: number) =>
  `/api/card-assets/${encodeURIComponent(sourceAssetId)}/files/preview?version=${version}`;
export const environmentAssetFileUrl = (sourceAssetId: string, kind: 'preview'|'blend'|'fbx', version: number) =>
  `/api/card-assets/${encodeURIComponent(sourceAssetId)}/files/${kind}?version=${version}`;

export const environmentSceneClient = {
  get: (projectId: string, signal?: AbortSignal) => requestJson<EnvironmentScene>(
    `/api/environment-scenes/${encodeURIComponent(projectId)}`, signal ? { signal } : {}),
  assets: (projectId: string, signal?: AbortSignal) => requestJson<ProjectAssetEntry[]>(
    `/api/project-assets?project_id=${encodeURIComponent(projectId)}`, signal ? { signal } : {}),
  renameAsset: (projectId: string, assetId: string, title: string, expectedUpdatedAt: string) =>
    requestJson<ProjectAssetEntry>(`/api/project-assets/${encodeURIComponent(assetId)}?project_id=${encodeURIComponent(projectId)}`, {
      method:'PUT', body:{title,expected_updated_at:expectedUpdatedAt},
    }),
  place: (projectId: string, body: {expected_version:number;asset_id:string;asset_version?:number}) =>
    requestJson<EnvironmentScene>(`/api/environment-scenes/${encodeURIComponent(projectId)}/objects`, { body }),
  transform: (projectId: string, objectId: string, body: {expected_version:number;transform:EnvironmentTransform}) =>
    requestJson<EnvironmentScene>(`/api/environment-scenes/${encodeURIComponent(projectId)}/objects/${encodeURIComponent(objectId)}`, { method:'PUT', body }),
  remove: (projectId: string, objectId: string, expectedVersion: number) =>
    requestJson<EnvironmentScene>(`/api/environment-scenes/${encodeURIComponent(projectId)}/objects/${encodeURIComponent(objectId)}`, {
      method:'DELETE', body:{expected_version:expectedVersion},
    }),
  aiBuild: (projectId: string, prompt: string, expectedVersion: number, requestId: string,
      sharedMemory: SharedProjectMemory, retryFailed = false) =>
    requestJson<AiBuildResult>(`/api/environment-scenes/${encodeURIComponent(projectId)}/ai-build`, {
      body:{request_id:requestId,expected_version:expectedVersion,prompt,shared_memory:sharedMemory,retry_failed:retryFailed},
    }),
};
