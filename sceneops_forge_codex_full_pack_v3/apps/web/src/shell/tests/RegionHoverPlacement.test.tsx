import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, test, vi } from 'vitest';
import { RegionPullHandles } from '../RegionPullHandles';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
test('hover waits without splitting, follows movement, confirms once and cancels on escape', async () => {
  vi.useFakeTimers();
  vi.stubGlobal("matchMedia", () => ({ matches: false }));
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  const split = vi.fn().mockResolvedValue(undefined);
  const pointer = (target: Element, type: string, x = 4, y = 200) => target.dispatchEvent(new MouseEvent(type, { bubbles: true, clientX: x, clientY: y }));
  try {
    await act(async () => root.render(<RegionPullHandles instanceId="test" split={split} getBounds={() => new DOMRect(0, 0, 800, 600)} />));
    expect(host.querySelectorAll('.forge-region-pull')).toHaveLength(3);
    expect(host.querySelector('.forge-edge-top')).toBeNull();
    const left = host.querySelector('.forge-edge-left')!;
    await act(async () => { pointer(left, 'pointerover'); vi.advanceTimersByTime(300); });
    expect(document.querySelector('.forge-hover-tool-card')).not.toBeNull();
    expect(document.querySelector('.forge-hover-placement')).toBeNull();
    await act(async () => pointer(left, 'pointerout'));
    await act(async () => vi.advanceTimersByTime(700));
    expect(document.querySelector('.forge-hover-tool-card')).toBeNull();
    await act(async () => pointer(left, 'pointerover'));
    await act(async () => vi.advanceTimersByTime(650));
    const overlay = document.querySelector('.forge-hover-placement')!;
    expect(overlay).not.toBeNull(); expect(split).not.toHaveBeenCalled();
    await act(async () => pointer(overlay, 'pointermove', 240, 200));
    await act(async () => vi.advanceTimersByTime(32));
    expect(document.querySelector('.forge-hover-split-preview path')!.getAttribute('d')).toContain('240,200');
    await act(async () => (overlay as HTMLElement).click());
    expect(split).toHaveBeenCalledExactlyOnceWith('test', 'left', 240, expect.objectContaining({ x: 240, y: 200 }));
    expect(document.querySelector('.forge-hover-placement')).toBeNull();
    await act(async () => pointer(left, 'pointerover'));
    await act(async () => vi.advanceTimersByTime(650));
    await act(async () => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })));
    expect(document.querySelector('.forge-hover-placement')).toBeNull();
    expect(split).toHaveBeenCalledTimes(1);
  } finally { await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); vi.unstubAllGlobals(); }
});

for (const [edge, origin, inward] of [
  ['left', [4, 200], [240, 200]],
  ['right', [796, 200], [560, 200]],
  ['bottom', [400, 596], [400, 360]],
] as const) {
  test(`${edge} can be pushed back without creating a region, then pulled again`, async () => {
    vi.useFakeTimers();
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    const host = document.createElement('div'); document.body.append(host);
    const root = createRoot(host), split = vi.fn().mockResolvedValue(undefined);
    const pointer = (target: Element, type: string, point: readonly number[]) => target.dispatchEvent(new MouseEvent(type, {
      bubbles: true, clientX: point[0], clientY: point[1],
    }));
    try {
      await act(async () => root.render(<RegionPullHandles instanceId="test" split={split} getBounds={() => new DOMRect(0, 0, 800, 600)} />));
      const handle = host.querySelector(`.forge-edge-${edge}`)!;
      await act(async () => pointer(handle, 'pointerover', origin));
      await act(async () => vi.advanceTimersByTime(650));
      const overlay = document.querySelector('.forge-hover-placement')!;
      await act(async () => pointer(overlay, 'pointermove', inward));
      await act(async () => vi.advanceTimersByTime(100));
      const curve = document.querySelector('.forge-hover-split-preview path')!.getAttribute('d')!;
      expect(curve).toContain(`${inward[0]},${inward[1]}`);
      expect(curve.match(/C/g)).toHaveLength(2);
      expect(curve.match(/L/g)).toHaveLength(2);
      await act(async () => pointer(overlay, 'pointermove', origin));
      expect(document.querySelector('.forge-hover-placement')).toBeNull();
      expect(document.querySelector('.forge-hover-retraction')).not.toBeNull();
      await act(async () => vi.advanceTimersByTime(300));
      expect(document.querySelector('.forge-hover-retraction')).toBeNull();
      expect(split).not.toHaveBeenCalled();
      await act(async () => pointer(handle, 'pointerout', origin));
      await act(async () => pointer(handle, 'pointerover', origin));
      await act(async () => vi.advanceTimersByTime(650));
      const next = document.querySelector('.forge-hover-placement')!;
      await act(async () => pointer(next, 'pointermove', inward));
      await act(async () => (next as HTMLElement).click());
      expect(split).toHaveBeenCalledExactlyOnceWith('test', edge, 240, expect.objectContaining({ x: inward[0], y: inward[1] }));
    } finally { await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); vi.unstubAllGlobals(); }
  });
}

test('failed animated placement clears the overlay and reports the failure', async () => {
  vi.useFakeTimers();
  vi.stubGlobal('matchMedia', () => ({ matches: false }));
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host), placed = vi.fn();
  const split = vi.fn().mockRejectedValue(new Error('无法创建分区'));
  try {
    await act(async () => root.render(<RegionPullHandles instanceId="test" split={split} onPlaced={placed} getBounds={() => new DOMRect(0, 0, 800, 600)} />));
    await act(async () => host.querySelector('.forge-edge-left')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })));
    await act(async () => (document.querySelector('.forge-hover-placement') as HTMLElement).click());
    await act(async () => vi.advanceTimersByTime(400));
    expect(host.querySelector('[role="alert"]')!.textContent).toBe('无法创建分区');
    expect(document.querySelector('.forge-hover-placement')).toBeNull();
    expect(placed).not.toHaveBeenCalled();
  } finally { await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); vi.unstubAllGlobals(); }
});

test('confirmation continues the same preview while native surfaces prepare', async () => {
  vi.useFakeTimers(); vi.stubGlobal('matchMedia', () => ({ matches: false }));
  const host = document.createElement('div'); document.body.append(host);
  const root = createRoot(host);
  let complete!: () => void;
  const split = vi.fn(() => new Promise<void>(resolve => { complete = resolve; }));
  const placed = vi.fn();
  try {
    await act(async () => root.render(<RegionPullHandles instanceId="test" split={split} onPlaced={placed} getBounds={() => new DOMRect(0,0,800,600)} />));
    await act(async () => host.querySelector('.forge-edge-left')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })));
    await act(async () => vi.advanceTimersByTime(32));
    const preview = document.querySelector('.forge-hover-split-preview')!;
    const originalCurve = preview.querySelector('path')!.getAttribute('d');
    await act(async () => (document.querySelector('.forge-hover-placement') as HTMLElement).click());
    await act(async () => vi.advanceTimersByTime(150));
    expect(preview.querySelector('path')!.getAttribute('d')).not.toBe(originalCurve);
    expect(document.querySelector('.forge-hover-split-preview')).toBe(preview);
    expect(document.querySelector('.is-confirming')).not.toBeNull();
    await act(async () => (document.querySelector('.forge-hover-placement') as HTMLElement).click());
    expect(split).toHaveBeenCalledTimes(1);
    const origin = (split.mock.calls[0] as unknown as [string, string, number, { onPrepared(): void }])[3];
    await act(async () => origin.onPrepared());
    expect(document.querySelector('.forge-hover-split-preview')).toBeNull();
    expect(placed).not.toHaveBeenCalled();
    await act(async () => complete());
    expect(placed).toHaveBeenCalledTimes(1);
  } finally { await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); vi.unstubAllGlobals(); }
});
