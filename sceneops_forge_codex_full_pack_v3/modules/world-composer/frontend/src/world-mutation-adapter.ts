import type { WorldExecutionMode } from './contracts.ts';
import type { WorldMutationPlan } from './placement.ts';

export interface WorldAdapterCapabilities {
  integrationId: string;
  adapterVersion: string;
  supportedCommands: WorldMutationPlan<unknown>['mutationKind'][];
  supportsRollback: boolean;
  maximumTimeoutMs: number;
  retryPolicy: { maximumAttempts: number; backoffMs: number };
  mode: WorldExecutionMode;
}

export interface WorldAdapterHealth {
  integrationId: string;
  state: 'connected' | 'disconnected';
  checkedAt: string;
  mode: WorldExecutionMode;
  message: string;
}

export interface ApprovedWorldMutation<TProposed> {
  commandId: string;
  correlationId: string;
  changeSetId: string;
  approvalId: string;
  approvedBy: string;
  approvedAt: string;
  plan: WorldMutationPlan<TProposed>;
}

export interface WorldMutationPreview {
  commandId: string;
  accepted: boolean;
  affectedSceneopsIds: string[];
  messages: string[];
  mode: WorldExecutionMode;
}

export interface WorldMutationResult extends WorldMutationPreview {
  snapshotId: string;
  logs: Array<{ timestamp: string; level: 'info' | 'warning' | 'error'; message: string }>;
  provenance: {
    integrationId: string;
    adapterVersion: string;
    changeSetId: string;
    approvalId: string;
    mode: WorldExecutionMode;
    executedAt: string;
  };
}

export interface WorldMutationValidation {
  passed: boolean;
  checks: Array<{ id: string; passed: boolean; message: string }>;
  mode: WorldExecutionMode;
}

export interface WorldMutationAdapter {
  healthCheck(): Promise<WorldAdapterHealth>;
  capabilities(): Promise<WorldAdapterCapabilities>;
  dryRun<TProposed>(command: ApprovedWorldMutation<TProposed>): Promise<WorldMutationPreview>;
  execute<TProposed>(
    command: ApprovedWorldMutation<TProposed>,
    signal: AbortSignal,
    onProgress?: (event: WorldMutationProgress) => void,
  ): Promise<WorldMutationResult>;
  validate(result: WorldMutationResult): Promise<WorldMutationValidation>;
  rollback(snapshotId: string): Promise<WorldMutationResult>;
}

export interface WorldMutationProgress {
  commandId: string;
  state: 'validating' | 'executing' | 'completed';
  progress: number;
  timestamp: string;
  mode: WorldExecutionMode;
}

export type WorldAdapterErrorCode =
  | 'APPROVAL_REQUIRED'
  | 'CANCELLED'
  | 'COMMAND_CONFLICT'
  | 'INTEGRATION_OFFLINE'
  | 'STALE_BASE'
  | 'UNKNOWN_SNAPSHOT';

export class WorldAdapterError extends Error {
  readonly code: WorldAdapterErrorCode;
  readonly retryable: boolean;

  constructor(code: WorldAdapterErrorCode, message: string, retryable: boolean) {
    super(message);
    this.name = 'WorldAdapterError';
    this.code = code;
    this.retryable = retryable;
  }
}

function assertApproved<TProposed>(command: ApprovedWorldMutation<TProposed>): void {
  if (!command.commandId || !command.correlationId || !command.changeSetId || !command.approvalId || !command.approvedBy) {
    throw new WorldAdapterError('APPROVAL_REQUIRED', 'APPROVAL_REQUIRED', false);
  }
  if (!command.approvedAt.endsWith('Z') || Number.isNaN(Date.parse(command.approvedAt))) {
    throw new Error('Approval timestamp must be UTC ISO-8601');
  }
  if (!command.plan.dryRunRequired) throw new Error('Dry-run cannot be bypassed');
}

export class DeterministicMockWorldMutationAdapter implements WorldMutationAdapter {
  readonly #executed = new Map<string, WorldMutationResult>();

  async healthCheck(): Promise<WorldAdapterHealth> {
    return {
      integrationId: 'world-mock',
      state: 'connected',
      checkedAt: '2026-09-04T00:00:00Z',
      mode: 'mock',
      message: 'Deterministic in-memory adapter; no external tool is connected.',
    };
  }

  async capabilities(): Promise<WorldAdapterCapabilities> {
    return {
      integrationId: 'world-mock',
      adapterVersion: '1.0.0',
      supportedCommands: [
        'world.scene-object.place',
        'world.graybox.apply',
        'world.procedural-placement.apply',
        'world.graph.update',
        'world.lighting-target.apply',
      ],
      supportsRollback: true,
      maximumTimeoutMs: 30_000,
      retryPolicy: { maximumAttempts: 2, backoffMs: 250 },
      mode: 'mock',
    };
  }

  async dryRun<TProposed>(command: ApprovedWorldMutation<TProposed>): Promise<WorldMutationPreview> {
    assertApproved(command);
    return {
      commandId: command.commandId,
      accepted: true,
      affectedSceneopsIds: [...command.plan.targetObjectIds],
      messages: ['Mock validation accepted the typed mutation plan.'],
      mode: 'mock',
    };
  }

  async execute<TProposed>(
    command: ApprovedWorldMutation<TProposed>,
    signal: AbortSignal,
    onProgress?: (event: WorldMutationProgress) => void,
  ): Promise<WorldMutationResult> {
    assertApproved(command);
    if (signal.aborted) throw new WorldAdapterError('CANCELLED', 'Operation cancelled', true);
    const existing = this.#executed.get(command.commandId);
    if (existing) {
      if (existing.provenance.changeSetId !== command.changeSetId) {
        throw new WorldAdapterError(
          'COMMAND_CONFLICT',
          'The command ID is already bound to a different ChangeSet.',
          false,
        );
      }
      return structuredClone(existing);
    }
    onProgress?.({
      commandId: command.commandId,
      state: 'validating',
      progress: 0.25,
      timestamp: '2026-09-04T00:00:00Z',
      mode: 'mock',
    });
    const preview = await this.dryRun(command);
    onProgress?.({
      commandId: command.commandId,
      state: 'executing',
      progress: 0.75,
      timestamp: '2026-09-04T00:00:01Z',
      mode: 'mock',
    });
    const result: WorldMutationResult = {
      ...preview,
      snapshotId: `mock-snapshot:${command.commandId}`,
      logs: [
        {
          timestamp: '2026-09-04T00:00:02Z',
          level: 'info',
          message: 'Executed only against the deterministic mock adapter.',
        },
      ],
      provenance: {
        integrationId: 'world-mock',
        adapterVersion: '1.0.0',
        changeSetId: command.changeSetId,
        approvalId: command.approvalId,
        mode: 'mock',
        executedAt: '2026-09-04T00:00:02Z',
      },
    };
    this.#executed.set(command.commandId, result);
    onProgress?.({
      commandId: command.commandId,
      state: 'completed',
      progress: 1,
      timestamp: '2026-09-04T00:00:02Z',
      mode: 'mock',
    });
    return structuredClone(result);
  }

  async validate(result: WorldMutationResult): Promise<WorldMutationValidation> {
    return {
      passed: result.accepted && result.mode === 'mock',
      checks: [
        {
          id: 'mock-result-mode',
          passed: result.mode === 'mock',
          message: 'Result remains explicitly labelled mock.',
        },
      ],
      mode: 'mock',
    };
  }

  async rollback(snapshotId: string): Promise<WorldMutationResult> {
    if (!snapshotId.startsWith('mock-snapshot:')) {
      throw new WorldAdapterError('UNKNOWN_SNAPSHOT', 'Unknown mock snapshot', false);
    }
    const original = this.#executed.get(snapshotId.slice('mock-snapshot:'.length));
    if (!original) throw new WorldAdapterError('UNKNOWN_SNAPSHOT', 'Unknown mock snapshot', false);
    return {
      commandId: `rollback:${snapshotId}`,
      accepted: true,
      affectedSceneopsIds: [],
      messages: ['Mock snapshot rollback completed.'],
      mode: 'mock',
      snapshotId,
      logs: [
        {
          timestamp: '2026-09-04T00:00:03Z',
          level: 'info',
          message: 'No external project data was changed.',
        },
      ],
      provenance: {
        ...original.provenance,
        executedAt: '2026-09-04T00:00:03Z',
      },
    };
  }
}
