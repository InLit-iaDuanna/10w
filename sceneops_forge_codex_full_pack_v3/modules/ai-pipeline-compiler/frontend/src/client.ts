import { requestJson } from '@sceneops/api-client';
import type { components } from './generated/harness-api';
export type Proposal = components['schemas']['PipelineProposal'];
export type Run = components['schemas']['PipelineRun'];
export type PlanRequest = components['schemas']['PlanningRequest'];
export type ModuleId = NonNullable<PlanRequest['module_ids']>[number];
export type RunAction = components['schemas']['RunAction'];
export type Catalog = components['schemas']['HarnessCatalog'];
export type Workflow = components['schemas']['DistilledWorkflow'];
export type Recovery = components['schemas']['RecoveryResponse'];
export type ModelProfile = components['schemas']['ModelProfile'];
const project = (id: string) => `/api/harness/projects/${encodeURIComponent(id)}`;
export const harnessKeys = {
  catalog: ['harness', 'catalog'] as const,
  proposals: (id: string) => ['harness', id, 'proposals'] as const,
  runs: (id: string) => ['harness', id, 'runs'] as const,
  templates: (id: string) => ['harness', id, 'templates'] as const,
  events: (id: string, run: string) => ['harness', id, 'events', run] as const,
};
export const harness = {
  catalog: () => requestJson<Catalog>('/api/harness/catalog'),
  saveProfile: (tier: ModelProfile['tier'], model: string | null) => requestJson<ModelProfile>(`/api/harness/model-profiles/${tier}`, {method:'PUT',body:{model}}),
  proposals: (id: string) => requestJson<Proposal[]>(`${project(id)}/proposals`),
  propose: (body: PlanRequest, signal: AbortSignal) => requestJson<Proposal>('/api/harness/proposals', {body, signal}),
  runs: (id: string) => requestJson<Run[]>(`${project(id)}/runs`),
  start: (id: string, proposal: string, requestId: string) => requestJson<Run>(`${project(id)}/proposals/${encodeURIComponent(proposal)}/runs`, {body:{request_id:requestId}}),
  action: (id: string, run: string, body: RunAction) => requestJson<Run>(`${project(id)}/runs/${encodeURIComponent(run)}/actions`, {body}),
  events: (id: string, run: string) => requestJson<components['schemas']['HarnessEvent'][]>(`${project(id)}/runs/${encodeURIComponent(run)}/events`),
  observe: (id: string, run: string) => requestJson<components['schemas']['RunObservation']>(`${project(id)}/runs/${encodeURIComponent(run)}/observation`),
  recover: (id: string, run: string, signal: AbortSignal) => requestJson<Recovery>(`${project(id)}/runs/${encodeURIComponent(run)}/recovery`, {body:{}, signal}),
  distill: (id: string, run: string, title: string) => requestJson<Workflow>(`${project(id)}/runs/${encodeURIComponent(run)}/distill`, {body:{title}}),
  templates: (id: string) => requestJson<Workflow[]>(`${project(id)}/templates`),
};
