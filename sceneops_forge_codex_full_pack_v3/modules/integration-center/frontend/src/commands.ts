import type {
  IntegrationCenterClient,
  IntegrationQueryContext,
  RecoveryCommandInput,
} from "./client.ts";
import type { IntegrationHealthView, RecoveryResultView } from "./types.ts";

export interface CommandContext {
  permissions: ReadonlySet<string>;
  projectId?: string;
}

export interface CommandAvailability {
  available: boolean;
  reason?: string;
}

export interface CommandDefinition<Input, Result> {
  id: string;
  title: string;
  requiredPermissions: string[];
  canExecute(context: CommandContext, input: Input): CommandAvailability;
  execute(
    client: IntegrationCenterClient,
    context: CommandContext,
    input: Input,
    signal: AbortSignal,
  ): Promise<Result>;
}

export interface OpenEditorResult {
  type: "workbench.open_editor";
  editorId: string;
  placement: "right" | "bottom";
  context?: Record<string, string>;
  requireConfirmation: boolean;
}

function permission(context: CommandContext, id: string): CommandAvailability {
  return context.permissions.has(id)
    ? { available: true }
    : { available: false, reason: `缺少 ${id} 权限。` };
}

export const refreshHealthCommand: CommandDefinition<IntegrationQueryContext, readonly IntegrationHealthView[]> = {
  id: "integration.health.refresh",
  title: "重新探测集成健康",
  requiredPermissions: ["integration:read"],
  canExecute(context, input) {
    const allowed = permission(context, "integration:read");
    if (!allowed.available) return allowed;
    if (!context.projectId) return { available: false, reason: "未选择项目。" };
    if (context.projectId !== input.projectId) return { available: false, reason: "项目上下文不匹配。" };
    return { available: true };
  },
  execute: (client, _context, input, signal) => client.listHealth(input, signal),
};

function openCommand(
  id: string,
  title: string,
  editorId: string,
  placement: "right" | "bottom",
  permissionId: string,
): CommandDefinition<Record<string, string>, OpenEditorResult> {
  return {
    id,
    title,
    requiredPermissions: [permissionId],
    canExecute(context) {
      const allowed = permission(context, permissionId);
      if (!allowed.available) return allowed;
      if (!context.projectId) return { available: false, reason: "未选择项目。" };
      return { available: true };
    },
    async execute(_client, _context, input) {
      return {
        type: "workbench.open_editor",
        editorId,
        placement,
        context: input,
        requireConfirmation: true,
      };
    },
  };
}

export const openLogsCommand = openCommand(
  "integration.open_logs",
  "打开关联日志",
  "observability.logs",
  "bottom",
  "observability:read",
);
export const openSetupCommand = openCommand(
  "integration.open_setup",
  "打开集成设置与恢复说明",
  "documentation",
  "right",
  "integration:read",
);
export const restartGuidanceCommand = openCommand(
  "worker.restart.guidance",
  "打开 Worker 安全重启说明",
  "documentation",
  "right",
  "job:read",
);

function recoveryCommand(
  id: "job.cancel" | "job.retry" | "job.resume",
  title: string,
  invoke: (
    client: IntegrationCenterClient,
    input: RecoveryCommandInput,
    signal: AbortSignal,
  ) => Promise<RecoveryResultView>,
): CommandDefinition<RecoveryCommandInput, RecoveryResultView> {
  return {
    id,
    title,
    requiredPermissions: ["job:operate"],
    canExecute(context, input) {
      const allowed = permission(context, "job:operate");
      if (!allowed.available) return allowed;
      if ((id === "job.retry" || id === "job.resume") && !input.attemptId) {
        return { available: false, reason: "重试或恢复需要新的 attemptId。" };
      }
      if (input.context.jobId !== input.jobId) {
        return { available: false, reason: "任务上下文与目标 jobId 不一致。" };
      }
      if (!context.projectId) return { available: false, reason: "未选择项目。" };
      if (context.projectId !== input.context.projectId) {
        return { available: false, reason: "项目上下文不匹配。" };
      }
      return { available: true };
    },
    execute: (client, _context, input, signal) => invoke(client, input, signal),
  };
}

export const cancelJobCommand = recoveryCommand("job.cancel", "取消任务", (client, input, signal) =>
  client.cancel(input, signal),
);
export const retryJobCommand = recoveryCommand("job.retry", "安全重试任务", (client, input, signal) =>
  client.retry(input, signal),
);
export const resumeJobCommand = recoveryCommand("job.resume", "从检查点恢复任务", (client, input, signal) =>
  client.resume(input, signal),
);

export const integrationCenterCommands = [
  refreshHealthCommand,
  openLogsCommand,
  openSetupCommand,
  cancelJobCommand,
  retryJobCommand,
  resumeJobCommand,
  restartGuidanceCommand,
] as const;
