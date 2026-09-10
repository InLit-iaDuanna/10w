import { requestJson, type JsonRequestOptions } from '@sceneops/api-client';
import type { components } from './generated/experience-api';
type ResponseFields<T> = T extends Array<infer Item> ? ResponseFields<Item>[] : T extends object ? { [Key in keyof T]-?: ResponseFields<T[Key]> } : T;
export type ProjectMemoryCollection = ResponseFields<components['schemas']['ProjectMemoryCollection']>;
export type MemoryEvent = ResponseFields<components['schemas']['MemoryEvent']>;
export type MemoryActivity = ResponseFields<components['schemas']['MemoryActivity']>;
export type MemoryWrite = components['schemas']['MemoryWrite'];
export type ExperienceTopic = ResponseFields<components['schemas']['ExperienceTopic']>;
export type ExperienceEntry = ResponseFields<components['schemas']['ExperienceEntry']>;
export type ExperienceUse = ResponseFields<components['schemas']['ExperienceUse']>;
export type ExperienceSettings = ResponseFields<components['schemas']['ExperienceSettings']>;
export type ExperienceStatus = ResponseFields<components['schemas']['ExperienceStatus']>;
export type ExperienceRevision = ResponseFields<components['schemas']['ExperienceRevision']>;
export type ExperiencePatch = components['schemas']['EntryUpdate'];
export type ExperienceSettingsPatch = components['schemas']['ExperienceSettingsUpdate'];
const query = (projectId: string | null, values: Record<string, string> = {}) => {
  const params = new URLSearchParams(values);
  if (projectId) params.set('project_id', projectId);
  return `?${params}`;
};
const json = (method: NonNullable<JsonRequestOptions['method']>, body: unknown): JsonRequestOptions => ({method, body});
export const experienceApi = {
  topics: () => requestJson<ExperienceTopic[]>('/api/experience/topics'),
  status: () => requestJson<ExperienceStatus>('/api/experience/status'),
  settings: (body: ExperienceSettingsPatch) => requestJson<ExperienceSettings>('/api/experience/settings', json('PUT', body)),
  entries: (projectId: string | null, q: string, scope: string, disabled: boolean) => requestJson<ExperienceEntry[]>(`/api/experience/entries${query(projectId, {q,scope,include_disabled:String(disabled)})}`),
  entry: (projectId: string | null, id: string) => requestJson<ExperienceEntry>(`/api/experience/entries/${encodeURIComponent(id)}${query(projectId)}`),
  revisions: (projectId: string | null, id: string) => requestJson<ExperienceRevision[]>(`/api/experience/entries/${encodeURIComponent(id)}/revisions${query(projectId)}`),
  patch: (projectId: string | null, id: string, body: ExperiencePatch) => requestJson<ExperienceEntry>(`/api/experience/entries/${encodeURIComponent(id)}${query(projectId)}`, json('PATCH', body)),
  restore: (projectId: string | null, id: string, expected_revision: number, revision: number) => requestJson<ExperienceEntry>(`/api/experience/entries/${encodeURIComponent(id)}/restore${query(projectId)}`, json('POST', {expected_revision,revision})),
  learn: (projectId: string | null) => requestJson<ExperienceStatus>('/api/experience/learn', json('POST', {project_id:projectId})),
  projectMemory: (projectId: string) => requestJson<ProjectMemoryCollection>(`/api/experience/project-memory${query(projectId)}`),
  remember: (body: MemoryWrite) => requestJson<MemoryEvent>('/api/experience/memories', json('POST', body)),
  activity: (projectId: string | null, originKey: string) => requestJson<MemoryActivity>(`/api/experience/activity${query(projectId,{origin_key:originKey})}`),
  undo: (projectId: string | null, eventId: string, expected_revision: number) => requestJson<MemoryEvent>(`/api/experience/events/${encodeURIComponent(eventId)}/undo`,json('POST',{project_id:projectId,expected_revision})),
  uses: (projectId: string | null, useKey: string, exact = true) => requestJson<ExperienceUse[]>(`/api/experience/uses${query(projectId, {use_key:useKey,exact:String(exact)})}`),
};

export const experienceEvidenceLabels: Record<string,string> = {historical:'源项目历史',user_statement:'用户陈述',reported:'报告结果',observed:'已观察',verified:'已验证',unknown:'未知'};

export const experienceStatusLabels: Record<string,string> = {unverified:'未验证',supported:'有证据支持',disputed:'存在争议',superseded:'已被替代'};
export const experienceKindLabels: Record<string,string> = {fact:'事实',case:'案例',procedure:'方法'};
