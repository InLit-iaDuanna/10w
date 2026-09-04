import type { LogFilterState, StructuredLogView } from "./types.ts";

export interface EventReconnectResult {
  nextCursor: string;
  resetRequired: boolean;
  events: readonly unknown[];
}

export interface ObservabilityClient {
  searchLogs(projectId: string, filters: LogFilterState, signal: AbortSignal): Promise<readonly StructuredLogView[]>;
  reconnectEvents(projectId: string, cursor: string | undefined, signal: AbortSignal): Promise<EventReconnectResult>;
  downloadDiagnosticBundle(projectId: string, correlationId?: string): Promise<Blob>;
}
