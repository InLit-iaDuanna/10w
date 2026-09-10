import assert from 'node:assert/strict';
import {test} from 'node:test';
import {ApiError, requestJson} from '../index.ts';

test('bodyless writes carry JSON content type and DELETE accepts an empty 204 response', async t => {
  const requests: RequestInit[] = [];
  t.mock.method(globalThis, 'fetch', async (_path: unknown, init: RequestInit) => {
    requests.push(init);
    return new Response(null, {status: 204});
  });
  for (const method of ['DELETE', 'POST', 'PUT', 'PATCH'] as const) {
    assert.equal(await requestJson('/api/fixture', {method}), undefined);
    const request = requests.at(-1)!;
    assert.equal(request.method, method);
    assert.equal(new Headers(request.headers).get('Content-Type'), 'application/json');
    assert.equal(request.body, undefined);
  }
  await requestJson('/api/fixture');
  assert.equal(new Headers(requests.at(-1)!.headers).has('Content-Type'), false);
});

test('failed removal preserves the API error for the project window', async t => {
  t.mock.method(globalThis, 'fetch', async () => new Response(JSON.stringify({detail: '文件夹项目不存在。'}), {status: 404}));
  await assert.rejects(requestJson('/api/fixture', {method: 'DELETE'}), error =>
    error instanceof ApiError && error.status === 404 && error.message === '文件夹项目不存在。');
});
