import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test, vi } from 'vitest';
import { WorkspaceEdgeIntro } from '../WorkspaceEdgeIntro';
Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
test('first visit teaches real placement and remembers only successful completion or dismissal', async () => {
  localStorage.clear(); vi.useFakeTimers();
  vi.stubGlobal("matchMedia", () => ({ matches: false }));
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  const split = vi.fn().mockRejectedValueOnce(new Error('无法打开')).mockResolvedValue(undefined);
  const render = () => root.render(<WorkspaceEdgeIntro instanceId="test" split={split} getBounds={() => new DOMRect(0,0,800,600)} />);
  const button = (text: string) => [...host.querySelectorAll('button')].find(e=>e.textContent?.includes(text))!;
  const place = async () => {
    await act(async () => host.querySelector('.forge-edge-right')!.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})));
    await act(async () => (document.querySelector('.forge-hover-placement') as HTMLElement).click());
  };
  try {
    await act(async () => render());
    expect(host.querySelector('[role="dialog"]')).not.toBeNull();
    expect(host.querySelector('.forge-region-pull')).toBeNull();
    await act(async () => button('我来试一试').click());
    expect(host.querySelectorAll('.forge-region-pull')).toHaveLength(3);
    await place();
    expect(localStorage.getItem('sceneops.workspace-edge-intro')).toBeNull();
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('无法打开');
    await place();
    expect(localStorage.getItem('sceneops.workspace-edge-intro')).toBe('completed');
    expect(host.textContent).toContain('工具区已打开');
    await act(async () => button('开始使用').click());
    expect(host.querySelector('.edge-intro-coach')).toBeNull();
    await act(async () => root.render(null)); await act(async () => render());
    expect(host.querySelector('[role="dialog"]')).toBeNull();
  } finally { await act(async()=>root.unmount());host.remove();localStorage.clear();vi.useRealTimers();vi.unstubAllGlobals(); }
});
