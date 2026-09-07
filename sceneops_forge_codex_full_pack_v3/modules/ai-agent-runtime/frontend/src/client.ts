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
type Prepare = Omit<components['schemas']['PrepareAgentTask'], 'allow_browser_observation' | 'allow_browser_interaction'>
  & Partial<Pick<components['schemas']['PrepareAgentTask'], 'allow_browser_observation' | 'allow_browser_interaction'>>;
type Authorize = components['schemas']['AuthorizeAgentTask'];
export type GameProjectExecution = components['schemas']['GameProjectExecution'];
type GameOperation = components['schemas']['GameOperationRequest']['operation'];

export const agentTaskKeys = {
  list: (projectId: string | null) => ['agent-tasks', 'list', projectId] as const,
  detail: (taskId: string) => ['agent-tasks', taskId] as const,
  game: (taskId: string) => ['agent-tasks', taskId, 'game'] as const,
};
const root = '/api/agent/tasks';
export const agentTasks = {
  list: (projectId: string | null, signal?: AbortSignal) => requestJson<TaskList>(
    `${root}${projectId ? `?project_id=${encodeURIComponent(projectId)}` : ''}`, signal ? { signal } : {}),
  get: (id: string, signal?: AbortSignal) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}`, signal ? { signal } : {}),
  prepare: (body: Prepare) => requestJson<AgentTask>(root, { body }),
  authorize: (id: string, body: Authorize) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/authorize`, { body }),
  cancel: (id: string) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/cancel`, { body: {} }),
  resume: (id: string) => requestJson<AgentTask>(`${root}/${encodeURIComponent(id)}/resume`, { body: {} }),
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
