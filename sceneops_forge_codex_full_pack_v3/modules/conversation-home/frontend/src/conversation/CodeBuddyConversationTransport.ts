import { requestJson } from '@sceneops/api-client';
import type { components } from '../generated/codebuddy-api.ts';
import { LocalConversationTransport } from '../fixtures/LocalConversationTransport.ts';
import { ConversationTransportError, type ConversationRequest, type ConversationRun, type ConversationStreamEvent, type ConversationTransport } from './transport.ts';

export type CodeBuddyModel = components['schemas']['ChatRequest']['model'];
export type CodeBuddyModelCatalog = components['schemas']['ModelCatalog'];
export class CodeBuddyConversationTransport implements ConversationTransport {
  selectedModel: 'mock' | CodeBuddyModel = 'mock';
  readonly #mock = new LocalConversationTransport();
  get availabilityMode() { return this.selectedModel === 'mock' ? 'mock' as const : 'planned' as const; }
  async start(request: ConversationRequest, signal: AbortSignal): Promise<ConversationRun> {
    if (this.selectedModel === 'mock') return this.#mock.start(request, signal);
    const body: components['schemas']['ChatRequest'] = { model: this.selectedModel, prompt: request.userMessage.body };
    let result: components['schemas']['ChatResponse'];
    try { result = await requestJson('/api/conversation/complete', { body, signal }); }
    catch (error) {
      if (signal.aborted) throw new DOMException('已取消', 'AbortError');
      throw new ConversationTransportError({ code: 'CODEBUDDY_UNAVAILABLE',
        message: error instanceof Error ? error.message : 'CodeBuddy 请求失败。', retryable: true,
        missingPermissions: [], missingIntegrations: ['codebuddycli'], suggestedActions: [] });
    }
    async function* events(): AsyncIterable<ConversationStreamEvent> {
      yield { type: 'text_delta', text: result.text };
      yield { type: 'completed' };
    }
    return { runId: `run_${request.userMessage.messageId.replace(/^msg_/, '')}`, mode: result.mode, events: events() };
  }
}
export function getCodeBuddyModels(signal?: AbortSignal): Promise<CodeBuddyModelCatalog> {
  return requestJson('/api/conversation/models', { signal });
}
