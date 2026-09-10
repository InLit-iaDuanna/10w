import {requestJson} from '@sceneops/api-client';
import type {components} from './generated/agent-api';
export type LocalServerInfo = components['schemas']['LocalServerInfo'];
export const localServerKey = ['local-servers'] as const;
export const localServers = {
  list: (signal?:AbortSignal) => requestJson<components['schemas']['LocalServerList']>('/api/agent/local-servers',{signal}),
  stop: (id:string) => requestJson<components['schemas']['LocalServerStopResult']>(`/api/agent/local-servers/${encodeURIComponent(id)}/stop`,{body:{}}),
};
