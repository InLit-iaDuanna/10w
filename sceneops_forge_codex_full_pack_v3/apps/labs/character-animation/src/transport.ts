import createClient from 'openapi-fetch';
import type { CharacterAnimationApiPort, CharacterAnimationPaths } from '@sceneops/character-animation';

const client = createClient<CharacterAnimationPaths>({ baseUrl: '' });
export const api: CharacterAnimationApiPort = {
  async post<TRequest, TResult>(path: Parameters<CharacterAnimationApiPort['post']>[0], request: TRequest): Promise<TResult> {
    const { data, error, response } = await client.POST(path, {
      body: request as never, signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) throw new Error(`请求失败 (${response.status})：${JSON.stringify(error)}`);
    return data as TResult;
  },
};
