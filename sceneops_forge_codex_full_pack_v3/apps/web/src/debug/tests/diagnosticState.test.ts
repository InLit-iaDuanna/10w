import assert from 'node:assert/strict';
import test from 'node:test';
import { UiDiagnosticBuffer, selectUiDiagnosticFields, summarizeUiError, type DiagnosticStorage } from '../diagnosticState.ts';

class MemoryStorage implements DiagnosticStorage {
  values = new Map<string, string>();
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
  removeItem(key: string) { this.values.delete(key); }
}

test('ring buffer persists only its newest bounded entries and restores them', () => {
  const storage = new MemoryStorage();
  const buffer = new UiDiagnosticBuffer(3, storage, 'test');
  buffer.record('edge-drag.begin', { edge: 'left' });
  buffer.record('edge-state.changed', { edge: 'left', size: 120 });
  buffer.record('edge-drag.end', { edge: 'left', size: 220 });
  buffer.record('edge-state.changed', { edge: 'left', mode: 'pinned' });
  const restored = new UiDiagnosticBuffer(3, storage, 'test');
  assert.deepEqual(restored.snapshot().map((entry) => entry.type), ['edge-state.changed', 'edge-drag.end', 'edge-state.changed']);
});

test('runtime field selection drops content-shaped and unknown properties', () => {
  const hostile = { edge: 'right', editorId: 'scene.viewport.3d', size: 240, requestBody: 'private chat', headers: { authorization: 'secret' }, token: 'secret', arbitrary: globalThis } as unknown as Parameters<typeof selectUiDiagnosticFields>[0];
  assert.deepEqual(selectUiDiagnosticFields(hostile), { edge: 'right', size: 240, editorId: 'scene.viewport.3d' });
});

test('error summaries save fixed classification and file frames without message or URL query', () => {
  const error = new TypeError('private chat failed at https://example.test/layout?token=secret');
  error.stack = 'TypeError: private chat\n    at resize (https://example.test/assets/app.js?key=secret:12:4)\n    at local (/src/drag.ts:30:2)';
  const result = summarizeUiError(error);
  assert.deepEqual(result, { summary: 'JavaScript error', errorName: 'TypeError', frames: ['/assets/app.js:12:4', '/src/drag.ts:30:2'] });
  assert.equal(JSON.stringify(result).includes('secret'), false);
  assert.equal(JSON.stringify(result).includes('private chat'), false);
});

test('non-Error rejection objects are never serialized', () => {
  assert.deepEqual(summarizeUiError({ body: 'private chat', token: 'secret' }), { summary: 'JavaScript error', errorName: 'Error', frames: [] });
});

test('storage failure degrades to memory and does not stop recording', () => {
  const storage: DiagnosticStorage = { getItem: () => null, setItem: () => { throw new Error('disabled'); }, removeItem: () => { throw new Error('disabled'); } };
  const buffer = new UiDiagnosticBuffer(2, storage);
  buffer.record('edge-drag.begin');
  assert.equal(buffer.snapshot().length, 1);
  assert.equal(buffer.storageStatus(), 'memory-only');
  buffer.clear();
  assert.equal(buffer.snapshot().length, 0);
});
