import { requestJson } from '@sceneops/api-client';
import type { components } from './generated/agent-api';

// Pydantic serializes defaults on responses; OpenAPI marks defaulted input
// properties optional. Derive response requiredness without copying the wire schema.
export type AgentTask = Required<components['schemas']['AgentTaskRecord']> & {
  authorization_card: Required<components['schemas']['AuthorizationCard']>;
  actions: Required<components['schemas']['ActionRecord']>[];
};
type TaskList = Omit<components['schemas']['AgentTaskList'], 'tasks'> & { tasks: AgentTask[] };
type TaskEvents = components['schemas']['AgentTaskEvents'];
type OptionalPrepareField = 'allow_browser_observation' | 'allow_browser_interaction'
  | 'allow_model_image_input' | 'include_demo_assets' | 'allow_blender_edit' | 'native_production' | 'permission_mode' | 'input_paths';
type Prepare = Omit<components['schemas']['PrepareAgentTask'], OptionalPrepareField>
  & Partial<Pick<components['schemas']['PrepareAgentTask'], OptionalPrepareField>>;
type Authorize = components['schemas']['AuthorizeAgentTask'];
export type UnityContentSnapshot = Required<components['schemas']['UnityContentSnapshot']>;
export type GameProjectExecution = components['schemas']['GameProjectExecution'];
type GameOperation = components['schemas']['GameOperationRequest']['operation'];

export const agentTaskKeys = {
  creationBrief: (taskId: string) => ['agent-tasks', taskId, 'creation-brief'] as const,
  source: (projectId: string, cardId: string) => ['card-source', projectId, cardId] as const,
  sourceFile: (projectId: string, cardId: string, path: string) => ['card-source', projectId, cardId, path] as const,
  unityContent: (taskId: string) => ['agent-tasks', taskId, 'unity-content'] as const,
  content: (taskId: string) => ['agent-tasks', taskId, 'demo-content'] as const,
  list: (projectId: string | null) => ['agent-tasks', 'list', projectId] as const,
  detail: (taskId: string) => ['agent-tasks', taskId] as const,
  game: (taskId: string) => ['agent-tasks', taskId, 'game'] as const,
};
const root = '/api/agent/tasks';
const sourceRoot = (projectId: string, cardId: string) => `/api/agent/projects/${encodeURIComponent(projectId)}/cards/${encodeURIComponent(cardId)}/source`;
function fileBase64(file: File) {
  return new Promise<string>((resolve,reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error('附件读取失败。'));
    reader.onload = () => {
      const value = String(reader.result ?? '');
      const separator = value.indexOf(',');
      if (separator < 0) reject(new Error('附件编码失败。'));
      else resolve(value.slice(separator + 1));
    };
    reader.readAsDataURL(file);
  });
}
export const agentTasks = {
  entities:(id:string)=>requestJson<components['schemas']['ProductionEntity'][]>(`${root}/${encodeURIComponent(id)}/production-entities`),
  adoptEntity:(id:string,entityId:string,body:components['schemas']['AdoptEntity'])=>requestJson<components['schemas']['ProductionEntity']>(`${root}/${encodeURIComponent(id)}/production-entities/${encodeURIComponent(entityId)}/adopt`,{body}),
  creationBrief: (id: string, signal?: AbortSignal) => requestJson<components['schemas']['CreationBrief']>(`${root}/${encodeURIComponent(id)}/creation-brief`, signal ? {signal} : {}),
  saveCreationBrief: (id: string, body: components['schemas']['SaveCreationBrief']) => requestJson<components['schemas']['CreationBrief']>(`${root}/${encodeURIComponent(id)}/creation-brief`, {method:'PUT', body}),
  archive: (id: string, body: components['schemas']['TaskArchiveRequest']) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/archive`, {method:'PUT', body}),
  progress: (projectId: string, archived: boolean, signal?: AbortSignal) => requestJson<TaskList>(`${root}?project_id=${encodeURIComponent(projectId)}&archived=${archived}`, signal ? {signal} : {}),
  prepareUnityAssetTask: (id: string, body: components['schemas']['PrepareUnityAssetTask']) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/unity-target`, {body}),
  readUnityContent: (id: string, signal?: AbortSignal) => requestJson<UnityContentSnapshot>(`${root}/${encodeURIComponent(id)}/unity-content`, signal ? {signal} : {}),
  manualUnityAction: (id: string, body: components['schemas']['UnityManualRequest']) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/unity-content`, {body}),
  sourceIndex: (projectId: string, cardId: string, signal?: AbortSignal) => requestJson<components['schemas']['CardSourceIndex']>(sourceRoot(projectId,cardId), signal ? {signal} : {}),
  sourceFile: (projectId: string, cardId: string, path: string, signal?: AbortSignal) => requestJson<components['schemas']['CardSourceFile']>(`${sourceRoot(projectId,cardId)}/file?path=${encodeURIComponent(path)}`, signal ? {signal} : {}),
  saveSource: (projectId: string, cardId: string, body: components['schemas']['SaveCardSource']) => requestJson<AgentTask>(`${sourceRoot(projectId,cardId)}/file`, {body}),
  uploadProjectInput: async (projectId: string, file: File) => requestJson<components['schemas']['NativeInputReference']>(
    `/api/agent/projects/${encodeURIComponent(projectId)}/inputs`, {body:{name:file.name,
      media_type:file.type || 'application/octet-stream',content_base64:await fileBase64(file)}}),
  blenderContent: (id: string, body: components['schemas']['BlenderManualRequest']) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/project-demo/blender`, {body}),
  requestDemoContinuation: (id: string, body: components['schemas']['DemoContinuationAuthorizationRequest']) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/project-demo/continuation-authorization`, {body}),
  content: (id: string, signal?: AbortSignal) => requestJson<components['schemas']['DemoContentIndex']>(`${root}/${encodeURIComponent(id)}/project-demo/content`, signal ? {signal} : {}),
  saveContent: (id: string, body: components['schemas']['DemoContentSave']) => requestJson<components['schemas']['DemoContentSaved']>(`${root}/${encodeURIComponent(id)}/project-demo/content`, {body}),
  playDemo: (id: string, candidateId: string) => requestJson<components['schemas']['DemoPlaySession']>(`${root}/${encodeURIComponent(id)}/project-demo/play`, {body:{candidate_id:candidateId}}),
  list: (projectId: string | null, signal?: AbortSignal) => requestJson<TaskList>(
    `${root}${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''}`, signal ? { signal } : {}),
  get: (id: string, signal?: AbortSignal) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}`, signal ? { signal } : {}),
  prepare: (body: Prepare) => requestJson<AgentTask>(root, { body }),
  authorize: (id: string, body: Authorize) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/authorize`, { body }),
  cancel: (id: string) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/cancel`, { body: {} }),
  resume: (id: string) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/resume`, { body: {} }),
  updateProjectDemo: (id: string) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/project-demo/update`, { body: {} }),
  continueProjectDemo: (id: string, body: components['schemas']['ContinueProjectDemoRequest']) =>
    requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/project-demo/continue`, { body }),
  gameStatus: (id: string, signal?: AbortSignal) => requestJson<GameProjectExecution>(
    `${root}/${encodeURIComponent(id)}/game`, signal ? { signal } : {}),
  gameOperation: (id: string, operation: GameOperation) => requestJson<GameProjectExecution>(
    `${root}/${encodeURIComponent(id)}/game`, { body: { operation } }),
  cancelObservation: (id: string) => requestJson<{cancel_requested: boolean}>(
    `${root}/${encodeURIComponent(id)}/game/observation/cancel`, {body:{}}),
  revokeObservation: (id: string) => requestJson<AgentTask>(
    `${root}/${encodeURIComponent(id)}/game/observation/revoke`, {body:{}}),
  interact: (id: string, body: components['schemas']['BrowserInteractionRequest']) => requestJson<GameProjectExecution>(
    `${root}/${encodeURIComponent(id)}/game/interaction`, {body}),
  revokeInteraction: (id: string) => requestJson<AgentTask>(
    `${root}/${encodeURIComponent(id)}/game/interaction/revoke`, {body:{}}),
  events: (id: string, after: number, signal?: AbortSignal) => requestJson<TaskEvents>(`${root}/${encodeURIComponent(id)}/events?after=${after}`, signal ? { signal } : {}),
  allEvents: async (id: string, signal?: AbortSignal): Promise<TaskEvents> => {
    const events: NonNullable<TaskEvents['events']> = [];
    let cursor = 0;
    while (true) {
      const page = await agentTasks.events(id, cursor, signal);
      events.push(...(page.events ?? []));
      if (!page.events?.length || page.next_cursor == null || page.next_cursor <= cursor) {
        return { events, next_cursor: cursor };
      }
      cursor = page.next_cursor;
    }
  },
};
