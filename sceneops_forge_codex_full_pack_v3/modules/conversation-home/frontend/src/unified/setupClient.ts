import { requestJson } from '@sceneops/api-client';
import type { components } from '../generated/unified-ai-api.ts';

export type CLISetupStatus = components['schemas']['CLISetupStatus'];
export type CLIProvider = CLISetupStatus['tools'][number]['provider'];
export const setupKey = ['unified-ai', 'local-setup'] as const;
export const readSetup = (signal?: AbortSignal) =>
  requestJson<CLISetupStatus>('/api/ai/setup', { signal });
export const installTools = (providers: CLIProvider[]) =>
  requestJson<CLISetupStatus>('/api/ai/setup/install', { body: { providers } });
export const loginTool = (provider: CLIProvider) =>
  requestJson<components['schemas']['LoginResponse']>('/api/ai/setup/login', { body: { provider } });
