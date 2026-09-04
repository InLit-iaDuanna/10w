import type { ObservabilityClient } from "./client.ts";
import type { LogFilterState, StructuredLogView } from "./types.ts";

export interface CommandContext {
  projectId?: string;
  correlationId?: string;
  permissions: ReadonlySet<string>;
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
  execute(client: ObservabilityClient, context: CommandContext, input: Input, signal: AbortSignal): Promise<Result>;
}

function requirePermission(context: CommandContext, permission: string): CommandAvailability {
  return context.permissions.has(permission)
    ? { available: true }
    : { available: false, reason: `缺少 ${permission} 权限。` };
}

export const searchLogsCommand: CommandDefinition<LogFilterState, readonly StructuredLogView[]> = {
  id: "observability.logs.search",
  title: "搜索结构化日志",
  requiredPermissions: ["observability:read"],
  canExecute(context) {
    const permission = requirePermission(context, "observability:read");
    if (!permission.available) return permission;
    if (!context.projectId) return { available: false, reason: "未选择项目。" };
    return { available: true };
  },
  execute(client, context, input, signal) {
    if (!context.projectId) throw new Error("projectId is required");
    return client.searchLogs(context.projectId, input, signal);
  },
};

export const exportDiagnosticCommand: CommandDefinition<Record<string, never>, Blob> = {
  id: "observability.diagnostic.export",
  title: "下载已脱敏诊断包",
  requiredPermissions: ["observability:export"],
  canExecute(context) {
    const permission = requirePermission(context, "observability:export");
    if (!permission.available) return permission;
    if (!context.projectId) return { available: false, reason: "未选择项目。" };
    return { available: true };
  },
  execute(client, context) {
    if (!context.projectId) throw new Error("projectId is required");
    return client.downloadDiagnosticBundle(context.projectId, context.correlationId);
  },
};

export const observabilityCommands = [searchLogsCommand, exportDiagnosticCommand] as const;
