import React, { act, StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test, vi } from 'vitest';
import { DemoExecutionRequest } from '../DemoExecutionRequest';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

test('aligned execution requires explicit consent even after rerender or a new round', async () => {
  const host = document.createElement('div');
  const root = createRoot(host);
  const prepare = vi.fn().mockResolvedValue(undefined);
  try {
    await act(async () => root.render(<StrictMode><DemoExecutionRequest alignmentId="round-one" prepare={prepare} /></StrictMode>));
    await act(async () => root.render(<StrictMode><DemoExecutionRequest alignmentId="round-one" prepare={() => prepare()} /></StrictMode>));
    expect(prepare).not.toHaveBeenCalled();
    await act(async () => host.querySelector('button')!.click());
    expect(prepare).toHaveBeenCalledTimes(1);
    expect(host.querySelector('button')).toBeNull();
    await act(async () => root.render(<StrictMode><DemoExecutionRequest alignmentId="round-two" prepare={prepare} /></StrictMode>));
    expect(prepare).toHaveBeenCalledTimes(1);
    await act(async () => host.querySelector('button')!.click());
    expect(prepare).toHaveBeenCalledTimes(2);
    expect(host.textContent).not.toContain('已执行');
  } finally { await act(async () => root.unmount()); }
});

test('failed confirmation preparation is visible and only retries on a click', async () => {
  const host = document.createElement('div');
  const root = createRoot(host);
  const prepare = vi.fn().mockRejectedValueOnce(new Error('服务未连接')).mockResolvedValue(undefined);
  try {
    await act(async () => root.render(<DemoExecutionRequest alignmentId="round-one" prepare={prepare} />));
    expect(prepare).not.toHaveBeenCalled();
    await act(async () => host.querySelector('button')!.click());
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('服务未连接');
    expect(prepare).toHaveBeenCalledTimes(1);
    await act(async () => host.querySelector('button')!.click());
    expect(prepare).toHaveBeenCalledTimes(2);
    expect(host.querySelector('[role="alert"]')).toBeNull();
  } finally { await act(async () => root.unmount()); }
});
