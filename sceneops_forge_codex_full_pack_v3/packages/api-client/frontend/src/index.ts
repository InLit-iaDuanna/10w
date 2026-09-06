export interface JsonRequestOptions {
  body?: unknown;
  signal?: AbortSignal;
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  headers?: HeadersInit;
  projectId?: string;
}

export interface BinaryJsonRequestOptions {
  body: BodyInit;
  signal?: AbortSignal;
  method?: 'POST' | 'PUT' | 'PATCH';
  headers?: HeadersInit;
  projectId?: string;
  timeoutMs?: number;
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

/** Send an already encoded body while keeping the shared local API error/cancellation boundary. */
export async function requestBinaryJson<T>(path: string, options: BinaryJsonRequestOptions): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.projectId) headers.set('X-SceneOps-Project', options.projectId);
  const timeout = AbortSignal.timeout(options.timeoutMs ?? 185000);
  const response = await fetch(path, {
    method: options.method ?? 'POST',
    headers,
    body: options.body,
    signal: options.signal ? AbortSignal.any([options.signal, timeout]) : timeout,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body?.message ?? (typeof body?.detail === 'string' ? body.detail : undefined);
    throw new ApiError(response.status, message ?? `本地文件请求失败（${response.status}），请检查启动终端。`);
  }
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
/** Consume server-sent JSON events through the same local proxy and cancellation boundary. */
export async function requestEventStream<T>(path: string, body: unknown, onEvent: (event: T) => void, signal: AbortSignal): Promise<void> {
  const response = await fetch(path, { method: 'POST', headers: { 'Accept': 'text/event-stream', 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal: AbortSignal.any([signal, AbortSignal.timeout(185000)]) });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(response.status, error?.message ?? error?.detail ?? '实时回复连接失败。');
  }
  if (response.headers.get('content-type')?.split(';')[0].trim() !== 'text/event-stream') {
    throw new ApiError(response.status, '本地 API 没有返回事件流。');
  }
  if (!response.body) throw new Error('回复没有可读取的事件流。');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      buffer = buffer.replace(/\r\n/g, '\n');
      let boundary;
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const data = frame.split('\n').filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
        if (data) onEvent(JSON.parse(data) as T);
      }
      if (done) break;
    }
  } finally { await reader.cancel().catch(() => undefined); reader.releaseLock(); }
}
