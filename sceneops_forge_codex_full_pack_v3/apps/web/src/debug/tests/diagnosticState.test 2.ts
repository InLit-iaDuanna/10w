import assert from 'node:assert/strict';
import test from 'node:test';
import { UiDiagnosticBuffer, selectUiDiagnosticFields, summarizeUiError } from '../diagnosticState.ts';

test('ring buffer retains only its newest bounded entries', () => {
  const buffer = new UiDiagnosticBuffer(3);
  buffer.record('drag.start', { edge: 'left' });
  buffer.record('drag.preview', { edge: 'left', size: 120 });
  buffer.record('drag.commit', { edge: 'left', size: 220 });
  buffer.record('drag.complete', { edge: 'left', mode: 'pinned' });
  assert.deepEqual(buffer.snapshot().map((entry) => entry.type), ['drag.preview', 'drag.commit', 'drag.complete']);
});

test('runtime field selection drops content-shaped and unknown properties', () => {
  const hostile = {
    edge: 'right', editorId: 'scene.viewport.3d', size: 240,
    requestBody: 'private chat', headers: { authorization: 'secret' }, token: 'secret', arbitrary: globalThis,
  } as unknown as Parameters<typeof selectUiDiagnosticFields>[0];
  assert.deepEqual(selectUiDiagnosticFields(hostile), {
    edge: 'right', size: 240, editorId: 'scene.viewport.3d',
  });
});

test('error summaries remove URL queries and sensitive header-shaped values', () => {
  const error = new Error('failed at https://example.test/layout?token=secret Authorization:Bearer-secret');
  error.stack = 'Error: failed\n    at resize (https://example.test/app.js?key=secret:12:4)';
  const result = summarizeUiError(error);
  assert.equal(result.summary.includes('secret'), false);
  assert.equal(result.summary.includes('?'), false);
  assert.equal(result.stack?.includes('secret'), false);
  assert.match(result.summary, /\[redacted\]/);
});

test('non-Error rejection objects are never serialized', () => {
  const result = summarizeUiError({ body: 'private chat', token: 'secret' });
  assert.deepEqual(result, { summary: 'Unhandled object error value' });
});

test('clear resets memory and notifies subscribers', () => {
  const buffer = new UiDiagnosticBuffer(2);
  let notifications = 0;
  const unsubscribe = buffer.subscribe(() => { notifications += 1; });
  buffer.record('drag.start');
  buffer.clear();
  unsubscribe();
  buffer.record('drag.end');
  assert.equal(notifications, 2);
  assert.equal(buffer.snapshot().length, 1);
});
