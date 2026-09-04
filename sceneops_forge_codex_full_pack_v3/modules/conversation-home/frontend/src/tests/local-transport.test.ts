import test from 'node:test';
import assert from 'node:assert/strict';
import { LocalConversationTransport, validateAssistantAction, ConversationTransportError } from '../index.ts';
const request = (body: string) => ({ conversationId: 'cnv_local', scope: { kind: 'pre_project' as const, sessionId: 'local' }, userMessage: {
  messageId: 'msg_local', role: 'user' as const, body, createdAt: '2026-09-04T00:00:00Z', mode: 'mock' as const, status: 'complete' as const, attachments: [], cards: [],
} });
test('mock tool request returns a validated proposal, without executing it', async () => {
  const run = await new LocalConversationTransport().start(request('打开工具库'), new AbortController().signal);
  assert.equal(run.mode, 'mock');
  const events = [];
  for await (const event of run.events) events.push(event);
  const added = events.find(e => e.type === 'card_added');
  assert.equal(added?.type, 'card_added');
  if (added?.type !== 'card_added' || added.card.kind !== 'assistant_action') throw new Error('Missing proposal');
  assert.equal(validateAssistantAction(added.card.action).ok, true);
  assert.equal(added.card.action.type, 'workbench.open_editor');
});
test('explicit mock error remains a visible retryable transport error', async () => {
  await assert.rejects(new LocalConversationTransport().start(request('模拟错误'), new AbortController().signal), error =>
    error instanceof ConversationTransportError && error.code === 'MOCK_TRANSPORT_FAILURE' && error.retryable);
});
