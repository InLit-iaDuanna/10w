import type { WorldExecutionMode } from './contracts.ts';

export interface ExecutionStatus {
  mode: WorldExecutionMode;
  state: 'ready' | 'running' | 'succeeded' | 'failed' | 'blocked';
  message: string;
  reason?: string;
}

const executionModes: ReadonlySet<string> = new Set([
  'live',
  'cached',
  'mock',
  'planned',
  'blocked',
]);

export function isWorldExecutionMode(value: unknown): value is WorldExecutionMode {
  return typeof value === 'string' && executionModes.has(value);
}

export function executionLabel(mode: WorldExecutionMode): string {
  const labels: Record<WorldExecutionMode, string> = {
    live: '实时',
    cached: '缓存',
    mock: '模拟',
    planned: '计划中',
    blocked: '受阻',
  };
  return labels[mode];
}

export function blockedStatus(message: string, reason: string): ExecutionStatus {
  return { mode: 'blocked', state: 'blocked', message, reason };
}
