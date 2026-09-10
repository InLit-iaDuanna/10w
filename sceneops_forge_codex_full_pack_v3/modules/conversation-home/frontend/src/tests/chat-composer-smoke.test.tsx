import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test } from 'vitest';
import { ChatComposer } from '@sceneops/core-ui';
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });

test('shared composer preserves the caller draft, controls and submit policy', async () => {
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  let submitted = 0;
  const render = (disabled: boolean) => <ChatComposer
    input={<textarea aria-label="对话草稿" defaultValue="保留原来的草稿" />}
    options={<button type="button">选择模型</button>}
    actions={<button type="submit" disabled={disabled}>发送</button>}
    onSubmit={event => { event.preventDefault(); submitted += 1; }} />;
  try {
    await act(async () => root.render(render(true)));
    await act(async () => host.querySelector<HTMLButtonElement>('button[type=submit]')!.click());
    expect(submitted).toBe(0);
    await act(async () => root.render(render(false)));
    expect(host.querySelector('textarea')!.value).toBe('保留原来的草稿');
    await act(async () => host.querySelector<HTMLButtonElement>('button[type=button]')!.click());
    expect(submitted).toBe(0);
    await act(async () => host.querySelector<HTMLButtonElement>('button[type=submit]')!.click());
    expect(submitted).toBe(1);
  } finally { await act(async () => root.unmount()); host.remove(); }
});
