import type {
  IntegrationHealthView,
  LogSummaryView,
  RecoveryResultView,
  WorkerView,
} from "./types.ts";

export interface IntegrationQueryContext {
  projectId: string;
  runId?: string;
  jobId?: string;
  correlationId: string;
  causationId: string;
}

export interface RecoveryCommandInput {
  jobId: string;
  attemptId?: string;
  idempotencyKey: string;
  context: IntegrationQueryContext;
}

export interface IntegrationCenterClient {
  listHealth(context: IntegrationQueryContext, signal: AbortSignal): Promise<readonly IntegrationHealthView[]>;
  listWorkers(projectId: string, signal: AbortSignal): Promise<readonly WorkerView[]>;
  listCorrelatedLogs(context: IntegrationQueryContext, signal: AbortSignal): Promise<readonly LogSummaryView[]>;
  cancel(input: RecoveryCommandInput, signal: AbortSignal): Promise<RecoveryResultView>;
  retry(input: RecoveryCommandInput, signal: AbortSignal): Promise<RecoveryResultView>;
  resume(input: RecoveryCommandInput, signal: AbortSignal): Promise<RecoveryResultView>;
}
