import { useEffect, useSyncExternalStore } from 'react';
import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { requestJson } from '@sceneops/api-client';
import type { components } from './generated/agent-api';
import type { AgentTask } from './client';

export type ProductionStep = Required<components['schemas']['ProductionStep']>;
export type ProductionArtifact = Required<components['schemas']['ProductionArtifact']>;
export type ProductionSnapshot = Omit<Required<components['schemas']['ProductionSnapshot']>, 'tasks' | 'steps' | 'artifacts'> & {
  tasks: AgentTask[]; steps: ProductionStep[]; artifacts: ProductionArtifact[];
};
type ConnectionState = 'connecting' | 'connected' | 'disconnected';
type Connection = { refs: number; state: ConnectionState; listeners: Set<() => void>; source?: EventSource; dirty: boolean; refreshing: boolean; closed: boolean };
const connections = new WeakMap<QueryClient, Map<string, Connection>>();
export const productionKeys = { snapshot: (projectId: string | null) => ['agent-production', projectId] as const };
const base = (project: string) => `/api/agent/projects/${encodeURIComponent(project)}`;
export const productionApi = {
  snapshot: (projectId: string, signal?: AbortSignal) => requestJson<ProductionSnapshot>(`${base(projectId)}/production`, signal ? { signal } : {}),
  artifactUrl: (artifact: ProductionArtifact) => `${base(artifact.project_id)}/artifacts/${encodeURIComponent(artifact.id)}/content?version=${artifact.version}`,
};

function connectionFor(client: QueryClient, project: string): Connection {
  let map = connections.get(client);
  if (!map) { map = new Map(); connections.set(client, map); }
  let value = map.get(project);
  if (!value) {
    value = { refs: 0, state: 'connecting', listeners: new Set(), dirty: false, refreshing: false, closed: false };
    map.set(project, value);
  }
  return value;
}

function updateConnection(connection: Connection, state: ConnectionState) {
  if (connection.state === state) return;
  connection.state = state;
  for (const notify of connection.listeners) notify();
}

async function refresh(client: QueryClient, project: string, connection: Connection) {
  connection.dirty = true;
  if (connection.refreshing) return;
  connection.refreshing = true;
  try {
    while (connection.dirty && !connection.closed) {
      connection.dirty = false;
      await client.invalidateQueries({ queryKey: productionKeys.snapshot(project) }, { cancelRefetch: false });
    }
  } finally { connection.refreshing = false; }
}

function attach(client: QueryClient, project: string, cursor: number) {
  const connection = connectionFor(client, project);
  connection.refs++;
  if (!connection.source) {
    connection.closed = false;
    updateConnection(connection, 'connecting');
    const source = new EventSource(`${base(project)}/events/stream?after=${cursor}`);
    connection.source = source;
    source.onopen = () => updateConnection(connection, 'connected');
    source.onerror = () => updateConnection(connection, 'disconnected');
    source.addEventListener('production', event => {
      try {
        const value: components['schemas']['AgentTaskEvent'] = JSON.parse((event as MessageEvent).data);
        if (value.project_id !== project) { source.close(); updateConnection(connection, 'disconnected'); return; }
        void refresh(client, project, connection);
      } catch { source.close(); updateConnection(connection, 'disconnected'); }
    });
  }
  return () => {
    if (--connection.refs === 0) {
      connection.closed = true;
      connection.source?.close();
      delete connection.source;
      updateConnection(connection, 'disconnected');
    }
  };
}

/** One project snapshot and one reference-counted stream, shared by every panel. */
export function useProduction(projectId: string | null) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: productionKeys.snapshot(projectId), enabled: !!projectId,
    queryFn: ({ signal }) => productionApi.snapshot(projectId!, signal), retry: false,
    staleTime: Infinity, refetchOnWindowFocus: false });
  const connection = projectId ? connectionFor(client, projectId) : null;
  const connectionState = useSyncExternalStore(
    notify => { connection?.listeners.add(notify); return () => { connection?.listeners.delete(notify); }; },
    () => connection?.state ?? 'disconnected', () => 'disconnected' as ConnectionState);
  const hasSnapshot = !!query.data;
  useEffect(() => {
    if (!projectId || !hasSnapshot) return;
    return attach(client, projectId, client.getQueryData<ProductionSnapshot>(productionKeys.snapshot(projectId))!.cursor);
  }, [client, projectId, hasSnapshot]);
  return { ...query, connectionState };
}
