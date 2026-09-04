import { z, type ZodType } from "zod";

import type {
  AddCommentRequest,
  AssignmentRequest,
  DecisionRequest,
  ObserveApprovalRequest,
} from "../generated/api-types.ts";
import type {
  CommandContext,
  CommandExecutionContext,
  WorkbenchCommandDefinition,
} from "../contracts.ts";
import {
  acquireLockSchema,
  addCommentSchema,
  assignmentSchema,
  createReviewSchema,
  decisionSchema,
  executeRollbackSchema,
  observeApprovalSchema,
  proposeRollbackSchema,
  releaseLinkSchema,
  releaseLockSchema,
} from "./schemas.ts";

type ReviewBody<T> = { readonly reviewId: string; readonly body: T };

export const commandDefinitions: readonly WorkbenchCommandDefinition[] = [
  command(
    "review.session.create",
    "创建评审会话",
    ["review:create"],
    ["git"],
    createReviewSchema,
    (context, input) => context.versionCollaborationApi.createReview(input),
  ),
  reviewCommand<AddCommentRequest>(
    "review.comment.add",
    "添加锚点评论",
    "review:comment",
    addCommentSchema,
    (context, input) =>
      context.versionCollaborationApi.addComment(input.reviewId, input.body),
  ),
  reviewCommand<AssignmentRequest>(
    "review.assignment.record",
    "记录评审分配",
    "review:assign",
    assignmentSchema,
    (context, input) =>
      context.versionCollaborationApi.recordAssignment(
        input.reviewId,
        input.body,
      ),
  ),
  reviewCommand<DecisionRequest>(
    "review.decision.record",
    "记录评审决定",
    "review:approve",
    decisionSchema,
    (context, input) =>
      context.versionCollaborationApi.recordDecision(
        input.reviewId,
        input.body,
      ),
  ),
  reviewCommand<ObserveApprovalRequest>(
    "review.approval.record",
    "记录已验证审批",
    "review:approve",
    observeApprovalSchema,
    (context, input) =>
      context.versionCollaborationApi.observeApproval(
        input.reviewId,
        input.body,
      ),
  ),
  command(
    "review.lock.acquire",
    "获取二进制资产锁",
    ["version:lock"],
    ["git", "git-lfs"],
    acquireLockSchema,
    (context, input) => context.versionCollaborationApi.acquireLock(input),
  ),
  command(
    "review.lock.release",
    "释放二进制资产锁",
    ["version:lock"],
    ["git", "git-lfs"],
    releaseLockSchema,
    (context, input) => context.versionCollaborationApi.releaseLock(input),
  ),
  command(
    "review.rollback.propose",
    "创建回滚 ChangeSet",
    ["version:rollback"],
    ["git"],
    proposeRollbackSchema,
    (context, input) =>
      context.versionCollaborationApi.proposeRollback(input),
  ),
  command(
    "review.rollback.execute",
    "执行已审批回滚",
    ["review:approve", "version:rollback"],
    ["git"],
    executeRollbackSchema,
    (context, input) =>
      context.versionCollaborationApi.executeRollback(input),
  ),
  command(
    "review.release.link",
    "链接获批变更与发布",
    ["review:approve"],
    [],
    releaseLinkSchema,
    (context, input) => context.versionCollaborationApi.linkRelease(input),
  ),
];

function reviewCommand<T>(
  id: string,
  title: string,
  permission: string,
  bodySchema: ZodType<T>,
  execute: (
    context: CommandExecutionContext,
    input: ReviewBody<T>,
  ) => Promise<unknown>,
): WorkbenchCommandDefinition {
  return command(
    id,
    title,
    [permission],
    [],
    z.object({ reviewId: z.string().min(3), body: bodySchema }).strict(),
    execute,
  );
}

function command<T>(
  id: string,
  title: string,
  requiredPermissions: readonly string[],
  requiredIntegrations: readonly string[],
  inputSchema: ZodType<T>,
  execute: (
    context: CommandExecutionContext,
    input: T,
  ) => Promise<unknown>,
): WorkbenchCommandDefinition {
  return {
    id,
    title,
    requiredPermissions,
    requiredIntegrations,
    inputSchema,
    canExecute: (context) =>
      availability(context, requiredPermissions, requiredIntegrations),
    execute: (context, input) => execute(context, inputSchema.parse(input)),
  };
}

function availability(
  context: CommandContext,
  permissions: readonly string[],
  integrations: readonly string[],
) {
  const missingPermission = permissions.find(
    (item) => !context.permissions.has(item),
  );
  if (missingPermission) {
    return {
      available: false,
      reason: `MISSING_PERMISSION:${missingPermission}`,
    };
  }
  const missingIntegration = integrations.find(
    (item) => !context.integrations.has(item),
  );
  if (missingIntegration) {
    return {
      available: false,
      reason: `INTEGRATION_OFFLINE:${missingIntegration}`,
    };
  }
  return { available: true };
}
