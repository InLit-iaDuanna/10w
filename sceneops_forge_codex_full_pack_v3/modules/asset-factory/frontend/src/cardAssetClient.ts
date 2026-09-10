import { requestBinaryJson, requestJson } from '@sceneops/api-client';
import type { components } from './generated/card-assets-api.ts';

export type AssetSource = 'import' | 'generated';
export type AssetStatus = 'processing' | 'ready' | 'failed';
export type PrimitivePart = components['schemas']['PrimitivePart'];
export type CardAssetProposal = components['schemas']['CardAssetProposal'];
export type CardAssetVersion = components['schemas']['CardAssetVersion'];
export type CardAssetRecord = components['schemas']['CardAssetRecord'];
export type CardAssetList = components['schemas']['CardAssetList'];
export type LiveModelUpdateRequest = components['schemas']['LiveModelUpdateRequest'];
export type LiveModelUpdateResult = components['schemas']['LiveModelUpdateResult'];
export type ProjectAssetEntry = components['schemas']['ProjectAssetEntry'];
export type SaveProjectAssetResult = components['schemas']['SaveProjectAssetResult'];

async function upload<T>(path: string, file: File, signal?: AbortSignal,
  headers: Record<string, string> = {}): Promise<T> {
  return requestBinaryJson<T>(path, {
    body: file,
    headers: {
      'Content-Type': 'application/octet-stream',
      'X-SceneOps-Filename': encodeURIComponent(file.name),
      ...headers,
    },
    signal,
  });
}

export const cardAssetKey = (projectId: string, cardId: string) => ['card-assets', projectId, cardId] as const;
export const projectAssetLibraryKey = (projectId: string) => ['project-assets', projectId] as const;
export const cardAssetFileUrl = (assetId: string, kind: 'preview'|'blend'|'fbx'|'source'|'manifest', version?: number) =>
  `/api/card-assets/${encodeURIComponent(assetId)}/files/${kind}${version ? `?version=${version}` : ''}`;

export const cardAssetClient = {
  list: (projectId: string, cardId: string, signal?: AbortSignal) => requestJson<CardAssetList>(
    `/api/card-assets?project_id=${encodeURIComponent(projectId)}&card_id=${encodeURIComponent(cardId)}`, {signal}),
  import: (projectId: string, cardId: string, sessionId: string, file: File, signal?: AbortSignal) => upload<CardAssetRecord>(
    `/api/card-assets/${encodeURIComponent(projectId)}/${encodeURIComponent(cardId)}/imports`, file, signal,
    {'X-SceneOps-Modeling-Session': sessionId}),
  reference: (projectId: string, cardId: string, file: File, signal?: AbortSignal) => upload<{id:string}>(
    `/api/card-assets/${encodeURIComponent(projectId)}/${encodeURIComponent(cardId)}/references`, file, signal),
  plan: (projectId: string, cardId: string, body: {session_id:string; transcript:{role:string;text:string}[]; reference_id?:string}) =>
    requestJson<CardAssetProposal>(`/api/card-assets/${encodeURIComponent(projectId)}/${encodeURIComponent(cardId)}/plans`, {body}),
  liveUpdate: (projectId: string, cardId: string, body: LiveModelUpdateRequest) =>
    requestJson<LiveModelUpdateResult>(`/api/card-assets/${encodeURIComponent(projectId)}/${encodeURIComponent(cardId)}/live-updates`,
      {body, timeoutMs:610000}),
  generate: (proposalId: string) => requestJson<CardAssetRecord>(
    `/api/card-assets/proposals/${encodeURIComponent(proposalId)}/generate`, {body:{}}),
  normalize: (assetId: string, target: number) => requestJson<CardAssetRecord>(
    `/api/card-assets/${encodeURIComponent(assetId)}/normalize`, {body:{target_extent_m:target}}),
  library: (projectId: string, signal?: AbortSignal) => requestJson<ProjectAssetEntry[]>(
    `/api/project-assets?project_id=${encodeURIComponent(projectId)}`, {signal}),
  saveToLibrary: (assetId: string, version: number,
    modelRotation?: NonNullable<LiveModelUpdateRequest['model_rotation_quaternion_xyzw']>) => requestJson<SaveProjectAssetResult>(
    `/api/card-assets/${encodeURIComponent(assetId)}/library`, {body:{version,
      ...(modelRotation ? {model_rotation_quaternion_xyzw:modelRotation} : {})}}),
};

export async function importProjectAssetFile(projectId: string, cardId: string, file: File,
    signal?: AbortSignal): Promise<ProjectAssetEntry> {
  const asset = await cardAssetClient.import(projectId, cardId, `scene-drop-${crypto.randomUUID()}`, file, signal);
  const saved = await cardAssetClient.saveToLibrary(asset.id, asset.current_version);
  return saved.entry;
}

export async function buildProjectAssetDraft(projectId: string, cardId: string, body: LiveModelUpdateRequest) {
  const result = await cardAssetClient.liveUpdate(projectId, cardId, body);
  return {version:result.asset.current_version,reused:result.reused};
}
