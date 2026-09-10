import { afterEach, expect, test, vi } from 'vitest';
import { animateRegionPlacement } from '../animateRegionPlacement';

afterEach(() => { document.body.replaceChildren(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function setup() {
  vi.stubGlobal('matchMedia', () => ({ matches: false }));
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => { queueMicrotask(() => callback(0)); return 1; });
  const root = document.createElement('main');
  root.innerHTML = '<div class="dv-groupview"></div><div class="dv-render-overlay"></div>';
  document.body.append(root);
  for (const element of root.children) element.getBoundingClientRect = () => new DOMRect(0, 48, 1200, 600);
  return root;
}

test('live chrome and sibling content both move, while incoming masks use the same workspace coordinates', async () => {
  const root = setup(), cancel = vi.fn();
  const prepared = vi.fn(() => expect(animate).toHaveBeenCalledTimes(4));
  const animate = vi.fn((_frames: Keyframe[]) => ({ finished: Promise.resolve(), cancel, startTime: null as number | null }));
  const region = document.createElement('div'), content = document.createElement('div');
  region.className = 'dv-groupview'; content.className = 'dv-render-overlay';
  region.getBoundingClientRect = () => new DOMRect(0, 48, 260, 600);
  content.getBoundingClientRect = () => new DOMRect(0, 80, 260, 568);
  for (const element of [...root.children, region, content]) Object.defineProperty(element, 'animate', { value: animate });
  await animateRegionPlacement(root, 'left', { x: 260, y: 300, shoulder: 180, startedAt: 100, onPrepared: prepared }, async () => {
    for (const element of root.children) element.getBoundingClientRect = () => new DOMRect(260, 48, 940, 600);
    root.append(region, content); return region;
  });
  expect(animate).toHaveBeenCalledTimes(4);
  expect(animate.mock.calls[0][0][0].transform).toContain('translate(-260px, 0px)');
  expect(animate.mock.calls[2][0][0].clipPath).toContain('260,252');
  expect(animate.mock.calls[3][0][0].clipPath).toContain('260,220');
  expect(animate.mock.calls.flatMap(call => call[0]).every(frame => frame.opacity === undefined)).toBe(true);
  expect(cancel).toHaveBeenCalledTimes(4);
  expect(prepared).toHaveBeenCalledTimes(1);
  expect(animate.mock.results.every(result => result.value.startTime === 100)).toBe(true);
  expect(animate.mock.calls.flatMap(call => call[0]).every(frame => !String(frame.transform).includes("scale"))).toBe(true);
});

test('a failed native split propagates the actual error without animating', async () => {
  const root = setup(), failure = new Error('无法创建分区');
  await expect(animateRegionPlacement(root, 'right', { x: 900, y: 300, shoulder: 180 }, async () => { throw failure; })).rejects.toBe(failure);
});
