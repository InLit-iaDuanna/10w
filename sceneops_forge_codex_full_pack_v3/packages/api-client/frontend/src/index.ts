export interface JsonRequestOptions {
  body?: unknown;
  signal?: AbortSignal;
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  headers?: HeadersInit;
  projectId?: string;
}

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message); }
}

export async function requestJson<T>(path: string, options: JsonRequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body !== undefined) headers.set('Content-Type', 'application/json');
  if (options.projectId) headers.set('X-SceneOps-Project', options.projectId);
  const response = await fetch(path, {
    method: options.method ?? (options.body === undefined ? 'GET' : 'POST'),
    headers,
    ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
    signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(125000)]) : AbortSignal.timeout(125000),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body?.message ?? (typeof body?.detail === 'string' ? body.detail : undefined);
    throw new ApiError(response.status, message ?? `本地 API 请求失败（${response.status}），请检查启动终端。`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/** Explicit per-editor transport, so pinned editors cannot leak another project's context. */
export function createProjectFetch(projectId: string): typeof fetch {
  return (input, init) => {
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined));
    headers.set('X-SceneOps-Project', projectId);
    return fetch(input, { ...init, headers });
  };
}
