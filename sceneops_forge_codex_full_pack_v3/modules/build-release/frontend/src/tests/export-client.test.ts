import assert from 'node:assert/strict';
import test from 'node:test';
import { exportApi } from '../export/client.ts';

test('export platform actions carry JSON and explicit project identity through the shared transport', async () => {
  const original = globalThis.fetch;
  const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
  globalThis.fetch = async (input, init) => {
    calls.push({ input, init });
    return new Response('{}', { headers: { 'Content-Type': 'application/json' } });
  };
  try {
    await exportApi.platformAction('project one', 'export-one', 'android', 'continue');
    await exportApi.platformAction('project one', 'export-one', 'android', 'cancel');
    await exportApi.refreshSource('project one', 'export-one');
    for (const call of calls) {
      assert.equal(call.init?.method, 'POST');
      assert.equal(new Headers(call.init?.headers).get('Content-Type'), 'application/json');
      assert.equal(new Headers(call.init?.headers).get('X-SceneOps-Project'), 'project one');
      assert.equal(call.init?.body, '{}');
      assert.match(String(call.input), /^\/api\/projects\/project%20one\/exports\/export-one\/(platforms\/android\/(continue|cancel)|refresh-source)$/);
    }
  } finally { globalThis.fetch = original; }
});

test('native execution and cancellation send explicit JSON authorization through shared transport', async () => {
  const original = globalThis.fetch;
  const calls: RequestInit[] = [];
  globalThis.fetch = async (_input, init) => {
    calls.push(init!);
    return new Response('{}', { headers: { 'Content-Type': 'application/json' } });
  };
  try {
    await exportApi.message('project', 'export', { content: '补齐 SDK 并继续', execution_mode: 'native', accept_full_access: true });
    await exportApi.message('project', 'export', { content: '解释这个错误', execution_mode: 'discuss', accept_full_access: false });
    await exportApi.cancelAgent('project', 'export');
    assert.deepEqual(calls.map(call => JSON.parse(call.body as string)), [
      { content: '补齐 SDK 并继续', execution_mode: 'native', accept_full_access: true },
      { content: '解释这个错误', execution_mode: 'discuss', accept_full_access: false }, {},
    ]);
    for (const call of calls) {
      assert.equal(call.method, 'POST');
      assert.equal(new Headers(call.headers).get('Content-Type'), 'application/json');
      assert.equal(new Headers(call.headers).get('X-SceneOps-Project'), 'project');
    }
  } finally { globalThis.fetch = original; }
});
