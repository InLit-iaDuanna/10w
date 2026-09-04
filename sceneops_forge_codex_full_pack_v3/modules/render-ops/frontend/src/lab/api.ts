import createClient from 'openapi-fetch';
import type { paths, components } from '../generated/lab-api';

export type LabState = components['schemas']['LabState'];
export type LabJob = components['schemas']['LabJob'];
export type LabImage = components['schemas']['LabImage'];
export type LabRecipeInput = components['schemas']['LabRecipeInput'];
export type LabProposalInput = components['schemas']['LabProposalInput'];
export type LabComparison = components['schemas']['LabComparison'];



async function result<T>(request: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const response = await request;
  if (!response.response.ok || response.data === undefined) {
    const payload = response.error as { detail?: unknown } | undefined;
    throw new Error(typeof payload?.detail === 'string' ? payload.detail
      : `操作未完成（HTTP ${response.response.status}），请检查输入后重试。`);
  }
  return response.data;
}

export function renderLabApi(session: string, fetchImpl: typeof fetch = fetch) {
  const client = createClient<paths>({ fetch: fetchImpl, headers: { 'X-Render-Lab': 'local-workbench' } });
  const path = { session_id: session };
  return {
    state: () => result(client.GET('/api/render-lab/{session_id}', { params: { path } })),
    plan: (body: LabRecipeInput) => result(client.POST('/api/render-lab/{session_id}/plan', { params: { path }, body })),
    jobAction: (job_id: string, action: 'load-fixture' | 'cancel' | 'retry') => result(client.POST(
      '/api/render-lab/{session_id}/jobs/{job_id}/actions/{action}', { params: { path: { ...path, job_id, action } } })),
    approveVariant: (job_id: string, variant_id: string) => result(client.POST(
      '/api/render-lab/{session_id}/jobs/{job_id}/variants/{variant_id}/approve', { params: { path: { ...path, job_id, variant_id } } })),
    propose: (job_id: string, body: LabProposalInput) => result(client.POST(
      '/api/render-lab/{session_id}/jobs/{job_id}/proposals', { params: { path: { ...path, job_id } }, body })),
    approveProposal: (job_id: string, proposal_id: string) => result(client.POST(
      '/api/render-lab/{session_id}/jobs/{job_id}/proposals/{proposal_id}/approve', { params: { path: { ...path, job_id, proposal_id } } })),
    compare: (job_id: string, before_id: string, after_id: string) => result(client.POST(
      '/api/render-lab/{session_id}/jobs/{job_id}/comparison', { params: { path: { ...path, job_id } }, body: { before_id, after_id } })),
    reset: () => result(client.POST('/api/render-lab/{session_id}/reset', { params: { path } })),
  };
}

export type RenderLabApi = ReturnType<typeof renderLabApi>;
