import { requestJson, requestArrayBuffer } from '@sceneops/api-client';
import type { components } from './generated/lookdev-api';
type Schemas = components['schemas'];
export type LookdevDocument = Schemas['LookdevDocument'];
export type LookdevTurn = Schemas['LookdevTurn'];
export type LookdevTarget = Schemas['LookdevTarget'];
export function createLookdevClient(projectId: string) {
  const base = `/api/lookdev/${encodeURIComponent(projectId)}`;
  const request = <T,>(url: string, body?: unknown, signal?: AbortSignal) => requestJson<T>(url, {body,signal,projectId});
  return {
    list: (target: LookdevTarget, signal?: AbortSignal) => request<LookdevDocument[]>(`${base}/documents?asset_id=${encodeURIComponent(target.asset_id)}${target.scene_instance_id ? `&scene_instance_id=${encodeURIComponent(target.scene_instance_id)}` : ''}`, undefined, signal),
    save: (document: LookdevDocument) => request<LookdevDocument>(`${base}/documents`, { document, expected_version: document.version } satisfies Schemas['SaveLookdevRequest']),
    propose: (body: Schemas['LookdevProposalRequest'], signal?: AbortSignal) => request<Schemas['LookdevProposal']>(`${base}/proposals`, body, signal),
    bindings: (signal?:AbortSignal) => request<Schemas['LookdevApplication'][]>(`${base}/bindings`,undefined,signal),
    history: (signal?: AbortSignal) => request<LookdevTurn[]>(`${base}/turns`,undefined,signal),
    finish: (turnId:string, body:Schemas['FinishLookdevTurnRequest']) => request<LookdevTurn>(`${base}/turns/${encodeURIComponent(turnId)}/finish`,body),
    apply: (body: Schemas['ApplyLookdevRequest']) => request<Schemas['LookdevApplication']>(`${base}/apply`, body),
    export: (body:Schemas['ExportLookdevRequest']) => request<Schemas['LookdevExport']>(`${base}/exports`,body),
    download: (artifact:Schemas['LookdevExport'],signal?:AbortSignal) => requestArrayBuffer(`${base}/exports/${encodeURIComponent(artifact.id)}/download`,{signal,projectId}),
    source: (target: LookdevTarget, signal?: AbortSignal) => requestArrayBuffer(`${base}/assets/${encodeURIComponent(target.asset_id)}/source?version=${target.asset_version}`, {signal,projectId}),
  };
}
