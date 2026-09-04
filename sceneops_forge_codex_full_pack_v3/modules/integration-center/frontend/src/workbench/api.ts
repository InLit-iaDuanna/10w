import createClient from 'openapi-fetch';
import type { paths, components } from '../generated/operations-api';


export type Snapshot = components['schemas']['OperationsSnapshot'];
export type Evidence = components['schemas']['LocalEvidence'];
export type Health = components['schemas']['IntegrationHealthSnapshot'];
export type Worker = components['schemas']['WorkerSnapshot'];
export type Filters = { project_id: string; job_id?: string; correlation_id?: string; text?: string };

export const operationsKeys = {
  snapshot: (filters: Filters) => ['integration-ops', 'snapshot', filters] as const,
  evidence: (project: string, artifact: string) => ['integration-ops', 'evidence', project, artifact] as const,
};

function failure(status: number): Error {
  if (status === 401 || status === 403) return new Error('访问未授权。请使用启动终端中的 Web 地址重新打开工作台。');
  if (status === 404) return new Error('当前项目中未找到该记录。');
  if (status === 422) return new Error('筛选参数格式不正确，请清除筛选后重试。');
  return new Error('本地 API 连接失败。请确认工作台启动命令仍在运行，然后重试。');
}

export function createOperationsClient(fetchImpl: typeof fetch = fetch) {
const client = createClient<paths>({ baseUrl: '', fetch: fetchImpl });
async function readSnapshot(filters: Filters, signal: AbortSignal): Promise<Snapshot> {
  const result = await client.GET('/api/v1/integration-ops/snapshot', { params: { query: filters }, signal });
  if (!result.data) throw failure(result.response.status);
  return result.data;
}

async function readEvidence(project: string, artifact: string, signal: AbortSignal): Promise<Evidence> {
  const result = await client.GET('/api/v1/integration-ops/evidence/{artifact_id}', {
    params: { path: { artifact_id: artifact }, query: { project_id: project } }, signal,
  });
  if (!result.data) throw failure(result.response.status);
  return result.data;
}

async function downloadDiagnostics(project: string, correlation?: string): Promise<void> {
  const result = await client.POST('/api/v1/observability/diagnostics', {
    body: { project_id: project, correlation_id: correlation || null }, parseAs: 'blob',
  });
  if (!result.response.ok || !result.data) throw failure(result.response.status);
  const url = URL.createObjectURL(result.data as Blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'sceneops-diagnostics-mock.zip';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
return { readSnapshot, readEvidence, downloadDiagnostics };
}
export const { readSnapshot, readEvidence, downloadDiagnostics } = createOperationsClient();
