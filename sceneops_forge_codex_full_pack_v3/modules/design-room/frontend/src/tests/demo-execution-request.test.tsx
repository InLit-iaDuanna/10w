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

test('project Demo agent shows its cumulative model and action budget before execution', async () => {
  const host = document.createElement('div');
  const root = createRoot(host);
  const prepare = vi.fn().mockResolvedValue(undefined);
  try {
    await act(async () => root.render(<DemoExecutionRequest alignmentId="direction-one"
      mode="project-demo-agent" prepare={prepare} />));
    expect(host.textContent).toContain('制作模型将按已确认方向选择内容与源码修改');
    expect(host.textContent).toContain('累计最多 28 次模型请求、32 个类型化动作和 30 分钟');
    expect(host.textContent).toContain('派生运行输入与构建产物不作为编辑源');
    expect(prepare).not.toHaveBeenCalled();
  } finally { await act(async () => root.unmount()); }
});
