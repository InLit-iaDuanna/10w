import createClient from 'openapi-fetch';
import type { LogicWorkbenchApi, WorldLogicApiPaths, WorldLogicApiComponents } from '../../../../modules/logic-studio/frontend/src/index.ts';
import type { WorldMutationPlan } from '../../../../modules/world-composer/frontend/src/index.ts';

const client = createClient<WorldLogicApiPaths>({ baseUrl: '' });
function result<T>(response: { data?: T; error?: unknown; response: Response }): T {
  if (response.error || !response.response.ok) {
    const detail = (response.error as { detail?: unknown })?.detail;
    throw new Error(typeof detail === 'string' ? detail : `本地 API 返回 ${response.response.status}：${JSON.stringify(detail ?? response.error)}`);
  }
  return response.data as T;
}
export const logicApi: LogicWorkbenchApi = {
  loadDemo: async () => result(await client.GET('/api/logic/demo')),
  validate: async graph => result(await client.POST('/api/logic/validate', { body: graph })),
  preview: async body => result(await client.POST('/api/logic/preview', { body })),
  propose: async body => result(await client.POST('/api/logic/proposals', { body })),
  proposeCode: async body => result(await client.POST('/api/logic/code-proposals', { body })),
};
export async function proposeWorld(plan: WorldMutationPlan<unknown>) {
  return result(await client.POST('/api/world/proposals', { body: plan as WorldLogicApiComponents['schemas']['WorldPlanRequest'] }));
}
