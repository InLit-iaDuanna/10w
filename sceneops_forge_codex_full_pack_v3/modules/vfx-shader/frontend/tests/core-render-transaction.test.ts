import assert from 'node:assert/strict';
import { test } from 'node:test';
import { validateRenderCandidate, withRenderLock } from '../src/core/render-transaction';

void test('error-scope rejection releases the render lock and the next transaction can run', async () => {
  const lock = { paused: false };
  const events: string[] = [];
  let rejectScope = true;
  const run = () => withRenderLock(lock, 'busy', () => validateRenderCandidate({
    compileAndDraw: async () => { events.push('draw'); },
    resetRenderTarget: () => { events.push('reset'); },
    popValidationError: async () => {
      events.push('pop');
      if (rejectScope) { rejectScope = false; throw new Error('清理异常'); }
      return null;
    },
    disposeTarget: () => { events.push('dispose'); },
  }));

  await assert.rejects(run(), /清理异常/);
  assert.equal(lock.paused, false);
  await run();
  assert.equal(lock.paused, false);
  assert.deepEqual(events, ['draw', 'reset', 'pop', 'dispose', 'draw', 'reset', 'pop', 'dispose']);
});

void test('cleanup failures retain the original render failure', async () => {
  await assert.rejects(withRenderLock({ paused: false }, 'busy', () => validateRenderCandidate({
    compileAndDraw: async () => { throw new Error('原始绘制错误'); },
    resetRenderTarget: () => { throw new Error('目标恢复错误'); },
    popValidationError: async () => null,
    disposeTarget: () => { throw new Error('目标释放错误'); },
  })), (error: Error) => {
    assert.match(error.message, /原始绘制错误/);
    assert.match(error.message, /目标恢复错误/);
    assert.match(error.message, /目标释放错误/);
    return true;
  });
});
