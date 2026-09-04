import type { components } from './generated/lab-api';
export type LabSnapshot = components['schemas']['LabSnapshot'];
export type LabAction = components['schemas']['LabAction'];
async function request<T>(path: string, body?: LabAction | components['schemas']['AdvisorRequest']): Promise<T> {
  const response = await fetch(`/api/${path}`, { method: body ? 'POST' : 'GET',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined });
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : result.message || JSON.stringify(result));
  return result;
}
export const labClient = { read: () => request<LabSnapshot>('workspace'),
  action: (body: LabAction) => request<LabSnapshot>('actions', body),
  models: () => request<components['schemas']['AdvisorCatalog']>('ai/models'),
  advise: (body: components['schemas']['AdvisorRequest']) => request<components['schemas']['AdvisorResult']>('ai/advice', body) };
export const advisorKeys = { models: ['concept-assets', 'ai-models'] as const };
export const labKeys = { workspace: ['concept-assets', 'workspace'] as const };
