import createClient from 'openapi-fetch';
import type { UiLabPaths, UiLabComponents } from '@sceneops/ui-studio';
import type { AudioLabPaths, AudioLabComponents } from '@sceneops/audio-studio-frontend';
import type { VfxLabPaths, VfxLabComponents } from '@sceneops/vfx-shader-frontend';

const session = sessionStorage.getItem('ui-audio-vfx-session') ?? crypto.randomUUID();
sessionStorage.setItem('ui-audio-vfx-session', session);
const options = { baseUrl: window.location.origin,
  headers: { 'X-Lab-Session': session, 'Content-Type': 'application/json' } };
export const ui = createClient<UiLabPaths>(options);
export const audio = createClient<AudioLabPaths>(options);
export const vfx = createClient<VfxLabPaths>(options);

export async function result<T>(request: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  let response;
  try { response = await request; } catch { throw new Error('本地 API 无法连接，请确认启动终端仍在运行后重试。'); }
  if (!response.response.ok || response.data === undefined) {
    const error = response.error as { detail?: unknown } | undefined;
    throw new Error(typeof error?.detail === 'string' ? error.detail : `请求未完成（${response.response.status}），请检查输入内容后重试。`);
  }
  return response.data;
}

export const uiApi = {
  check: (body: UiLabComponents['schemas']['Draft']) => result(ui.POST('/api/ui/check', { body })),
  propose: (body: UiLabComponents['schemas']['Draft']) => result(ui.POST('/api/ui/proposals', { body })),
};
export const audioApi = {
  fixture: () => result(audio.GET('/api/audio/fixture')),
  inspectFixture: () => result(audio.POST('/api/audio/inspect-fixture')),
  inspect: (body: AudioLabComponents['schemas']['Upload']) => result(audio.POST('/api/audio/inspect', { body })),
  propose: (body: AudioLabComponents['schemas']['BindingDraft']) => result(audio.POST('/api/audio/proposals', { body })),
};
export const vfxApi = {
  evaluate: (body: VfxLabComponents['schemas']['Draft']) => result(vfx.POST('/api/vfx/evaluate', { body })),
  propose: (body: VfxLabComponents['schemas']['Draft']) => result(vfx.POST('/api/vfx/proposals', { body })),
};
