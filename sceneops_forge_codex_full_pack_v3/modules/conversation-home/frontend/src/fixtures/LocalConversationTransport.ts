import type { ConversationRequest, ConversationRun, ConversationStreamEvent, ConversationTransport } from '../conversation/transport.ts';
import { ConversationTransportError } from '../conversation/transport.ts';

/** Explicit deterministic demo adapter: no LLM, no project or external-tool execution. */
export class LocalConversationTransport implements ConversationTransport {
  readonly availabilityMode = 'mock' as const;
  async start(request: ConversationRequest, signal: AbortSignal): Promise<ConversationRun> {
    const text = request.userMessage.body.trim();
    if (text === '模拟错误') throw new ConversationTransportError({
      code: 'MOCK_TRANSPORT_FAILURE', message: '确定性演示错误；可重试或发送其他内容。',
      retryable: true, missingPermissions: [], missingIntegrations: [], suggestedActions: [],
    });
    const id = request.userMessage.messageId.replace(/^msg_/, '');
    const editorId = text === '打开工具库' ? 'shell.tool-library' : text === '打开命令搜索' ? 'shell.command-search' : null;
    async function* events(): AsyncIterable<ConversationStreamEvent> {
      signal.throwIfAborted();
      yield { type: 'text_delta', text: editorId
        ? 'MOCK · 已生成打开工具的提案。请先预览，再确认；停靠操作由本地真实命令执行。'
        : 'MOCK · 当前未连接 LLM，使用确定性对话演示。请输入“打开工具库”或“打开命令搜索”，也可按 / 直接搜索。项目、构建及外部工具请在对应独立工作台操作。' };
      if (editorId) yield { type: 'card_added', card: {
        cardId: `card_${id}`, kind: 'assistant_action', mode: 'mock', title: text,
        action: { actionId: `act_${id}`, type: 'workbench.open_editor', title: text,
          requiresConfirmation: true, input: { editorId, placement: { mode: 'split', direction: 'right' } } },
      } };
      signal.throwIfAborted();
      yield { type: 'completed' };
    }
    return { runId: `run_${id}`, mode: 'mock', events: events() };
  }
}
