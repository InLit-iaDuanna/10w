export async function requestJson<T>(path: string, options: { body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.body === undefined ? 'GET' : 'POST',
    headers: { Accept: 'application/json', ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
    signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(125000)]) : AbortSignal.timeout(125000),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.message ?? `本地 API 请求失败（${response.status}），请检查启动终端。`);
  }
  return response.json() as Promise<T>;
}
