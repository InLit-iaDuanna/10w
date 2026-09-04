import { z } from "zod";

import type {
  CancelPlaytestInput,
  CommandAvailability,
  CommandAvailabilityContext,
  CompareRegressionInput,
  OpenIssueBackpinInput,
  ProposeIssueChangeInput,
  ReviewBackpinInput,
  RunPlaytestInput,
  WorkbenchCommandDefinition,
} from "../types.ts";

const stableId = z.string().min(3).max(160).regex(/^[A-Za-z0-9][A-Za-z0-9._:-]*$/);
const runId = z.string().min(3).max(96).regex(/^[A-Za-z0-9][A-Za-z0-9._:-]*$/);
const runnableExecutionMode = z.enum(["live", "cached", "mock"]);

const runInputSchema: z.ZodType<RunPlaytestInput> = z.object({
  runId,
  testCaseId: stableId,
  buildId: stableId,
  executionMode: runnableExecutionMode,
  replayActionIds: z.array(stableId),
}).strict();

const cancelInputSchema: z.ZodType<CancelPlaytestInput> = z.object({
  runId,
}).strict();

const openBackpinInputSchema: z.ZodType<OpenIssueBackpinInput> = z.object({
  issueId: stableId,
}).strict();

const proposeChangeInputSchema: z.ZodType<ProposeIssueChangeInput> = z.object({
  issueId: stableId,
}).strict();

const reviewBackpinInputSchema: z.ZodType<ReviewBackpinInput> = z.object({
  issueId: stableId,
  decision: z.enum(["confirm", "reject"]),
}).strict();

const comparisonInputSchema: z.ZodType<CompareRegressionInput> = z.object({
  comparisonId: stableId,
  baselineRunId: runId,
  candidateRunId: runId,
}).strict();

function availability(
  context: CommandAvailabilityContext,
  permission: string,
  needsRunner = false,
): CommandAvailability {
  if (!context.moduleEnabled) {
    return { available: false, code: "MODULE_DISABLED", message: "AI Playtest 模块已停用。" };
  }
  if (!context.grantedPermissions.includes(permission)) {
    return { available: false, code: "PERMISSION_DENIED", message: `缺少 ${permission} 权限。` };
  }
  if (needsRunner && context.requestedMode === "live" && !context.playtestRunnerAvailable) {
    return {
      available: false,
      code: "INTEGRATION_OFFLINE",
      message: "Live Playtest runner 未连接；Mock 不会显示为 Live。",
    };
  }
  if (needsRunner && context.requestedMode === "cached" && !context.cachedPlaytestAvailable) {
    return {
      available: false,
      code: "CACHED_RESULT_UNAVAILABLE",
      message: "没有可复用且来源已验证的真实历史运行。",
    };
  }
  return { available: true };
}

export function runAvailability(
  context: CommandAvailabilityContext,
  requestedMode = context.requestedMode,
): CommandAvailability {
  return availability({ ...context, requestedMode }, "playtest:run", true);
}

const runCommand: WorkbenchCommandDefinition<RunPlaytestInput, unknown> = {
  id: "playtest.run",
  title: "运行 AI Playtest",
  inputSchema: runInputSchema,
  requiredPermissions: ["playtest:run"],
  canExecute: (context, input) => runAvailability(context, input.executionMode),
  execute: (context, input) => context.playtestApi.run(input),
};

const cancelCommand: WorkbenchCommandDefinition<CancelPlaytestInput, unknown> = {
  id: "playtest.cancel",
  title: "取消 Playtest",
  inputSchema: cancelInputSchema,
  requiredPermissions: ["playtest:cancel"],
  canExecute: (context) => availability(context, "playtest:cancel"),
  execute: (context, input) => context.playtestApi.cancel(input),
};

const openBackpinCommand: WorkbenchCommandDefinition<OpenIssueBackpinInput, unknown> = {
  id: "playtest.issue.open-backpin",
  title: "打开问题回钉",
  inputSchema: openBackpinInputSchema,
  requiredPermissions: ["issue:read"],
  canExecute: (context) => availability(context, "issue:read"),
  execute: (context, input) => context.playtestApi.restoreIssue(input),
};

const proposeChangeCommand: WorkbenchCommandDefinition<ProposeIssueChangeInput, unknown> = {
  id: "playtest.changeset.propose",
  title: "提出 ChangeSet",
  inputSchema: proposeChangeInputSchema,
  requiredPermissions: ["changeset:propose"],
  canExecute: (context) => availability(context, "changeset:propose"),
  execute: (context, input) => context.playtestApi.beginChangeProposal(input),
};

const reviewBackpinCommand: WorkbenchCommandDefinition<ReviewBackpinInput, unknown> = {
  id: "playtest.issue.review-backpin",
  title: "审核问题回钉",
  inputSchema: reviewBackpinInputSchema,
  requiredPermissions: ["issue:write"],
  canExecute: (context) => availability(context, "issue:write"),
  execute: (context, input) => context.playtestApi.reviewBackpin(input),
};

const compareCommand: WorkbenchCommandDefinition<CompareRegressionInput, unknown> = {
  id: "playtest.regression.compare",
  title: "比较同配置运行",
  inputSchema: comparisonInputSchema,
  requiredPermissions: ["playtest:read"],
  canExecute: (context) => availability(context, "playtest:read"),
  execute: (context, input) => context.playtestApi.compare(input),
};

export const playtestCommands = [
  runCommand,
  cancelCommand,
  openBackpinCommand,
  reviewBackpinCommand,
  proposeChangeCommand,
  compareCommand,
] as const;
