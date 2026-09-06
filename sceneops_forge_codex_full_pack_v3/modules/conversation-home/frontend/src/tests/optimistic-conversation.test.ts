import assert from 'node:assert/strict';
import test from 'node:test';
import {
  createOutgoingAttempt,
  hasPendingAttempt,
  outgoingConversationReducer,
} from '../unified/outgoingConversation.ts';

const original = createOutgoingAttempt('local_1', '保留这条发送内容', '2026-09-05T08:00:00.000Z');

test('optimistic attempt is immediately pending and server success removes only that temporary row', () => {
  const pending = outgoingConversationReducer([], { type: 'started', attempt: original });
  assert.equal(pending[0]?.text, '保留这条发送内容');
  assert.equal(pending[0]?.status, 'pending');
  assert.equal(hasPendingAttempt(pending), true);

  const anotherFailure = { ...original, id: 'local_older', status: 'failed' as const };
  const reconciled = outgoingConversationReducer([anotherFailure, ...pending], {
    type: 'saved',
    attemptId: original.id,
  });
  assert.deepEqual(reconciled, [anotherFailure]);
});

test('failure and cancellation preserve sent text and retry never substitutes a new draft', () => {
  const failed = outgoingConversationReducer([original], {
    type: 'failed',
    attemptId: original.id,
    error: '服务暂时不可用',
  });
  assert.equal(failed[0]?.text, original.text);
  assert.equal(failed[0]?.error, '服务暂时不可用');

  const retried = outgoingConversationReducer(failed, { type: 'retried', attemptId: original.id });
  assert.equal(retried[0]?.text, original.text);
  assert.equal(retried[0]?.status, 'pending');
  assert.equal(retried[0]?.attemptNumber, 2);
  assert.equal(retried[0]?.error, undefined);

  const cancelled = outgoingConversationReducer(retried, {
    type: 'cancelled',
    attemptId: original.id,
    cause: 'user',
  });
  assert.equal(cancelled[0]?.text, original.text);
  assert.equal(cancelled[0]?.status, 'cancelled');
  assert.equal(cancelled[0]?.cancellationCause, 'user');
  assert.equal(hasPendingAttempt(cancelled), false);
});

test('an abort callback cannot overwrite the specific visible cancellation reason', () => {
  const contextCancelled = outgoingConversationReducer([original], {
    type: 'cancelled',
    attemptId: original.id,
    cause: 'context_changed',
  });
  const settledAbort = outgoingConversationReducer(contextCancelled, {
    type: 'cancelled',
    attemptId: original.id,
    cause: 'request_aborted',
  });
  assert.equal(settledAbort[0]?.cancellationCause, 'context_changed');
});

test('stream deltas remain provisional until the complete conversation is saved', () => {
  let attempts = outgoingConversationReducer([], { type: 'started', attempt: original });
  attempts = outgoingConversationReducer(attempts, {
    type: 'response_status', attemptId: original.id, text: '正在接收流式回复…',
  });
  attempts = outgoingConversationReducer(attempts, {
    type: 'response_delta', attemptId: original.id, text: '第一段',
  });
  attempts = outgoingConversationReducer(attempts, {
    type: 'response_delta', attemptId: original.id, text: '第二段',
  });
  assert.equal(attempts[0]?.responseText, '第一段第二段');
  assert.equal(attempts[0]?.streamStatus, '正在接收流式回复…');

  const interrupted = outgoingConversationReducer(attempts, {
    type: 'failed', attemptId: original.id, error: '连接中断',
  });
  assert.equal(interrupted[0]?.responseText, '第一段第二段');
  const retried = outgoingConversationReducer(interrupted, {
    type: 'retried', attemptId: original.id,
  });
  assert.equal(retried[0]?.responseText, undefined);
  assert.equal(retried[0]?.streamStatus, undefined);
});
