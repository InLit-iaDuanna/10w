import type {
  ExecutionMode,
  ReviewConversationSummary,
  ReviewSession,
} from "../generated/api-types.ts";

export type EditorSurfaceState =
  | "loading"
  | "empty"
  | "success"
  | "failed"
  | "offline"
  | "permission";

export interface ReviewEditorView {
  readonly state: EditorSurfaceState;
  readonly title: string;
  readonly message: string;
  readonly mode: ExecutionMode;
  readonly modeLabel: string;
  readonly retryCommandId: string | null;
  readonly conflictMessages: readonly string[];
}

export interface PresenterInput {
  readonly loading: boolean;
  readonly hasPermission: boolean;
  readonly gitConnected: boolean;
  readonly review: ReviewSession | null;
  readonly errorCode: string | null;
}

export function presentReview(input: PresenterInput): ReviewEditorView {
  if (!input.hasPermission) {
    return state("permission", "无权查看评审", "需要 review:read 权限。", "blocked", null);
  }
  if (input.loading) {
    return state("loading", "正在加载评审", "正在读取版本、差异与审计记录…", "planned", null);
  }
  if (input.errorCode) {
    return state("failed", "评审加载失败", structuredFailure(input.errorCode), "blocked", "review.refresh");
  }
  if (!input.gitConnected && !input.review) {
    return state("offline", "Git 未连接", "连接 Git 后可创建新评审；不会用 mock 冒充。", "blocked", "integration.open");
  }
  if (!input.review) {
    return state("empty", "暂无评审会话", "从对话或命令创建一个评审会话。", "planned", null);
  }
  return {
    state: "success",
    title: input.review.title,
    message: input.gitConnected
      ? `四层差异已封存于 ${input.review.diff.diff_bundle_id}。`
      : `正在离线读取已封存差异 ${input.review.diff.diff_bundle_id}；新 Git 状态不可用。`,
    mode: input.review.mode,
    modeLabel: modeLabel(input.review.mode),
    retryCommandId: null,
    conflictMessages: input.review.diff.conflicts.map((conflict) => conflict.message),
  };
}

export function presentConversationSummary(summary: ReviewConversationSummary): string {
  const blockers = summary.blocking_conflicts.length
    ? `阻塞：${summary.blocking_conflicts.join("；")}`
    : "无阻塞冲突";
  return `${summary.headline}\n${summary.layer_summaries.join("\n")}\n${blockers}`;
}

export function modeLabel(mode: ExecutionMode): string {
  return {
    live: "LIVE · 实际执行",
    cached: "CACHED · 真实历史结果",
    mock: "MOCK · 确定性夹具",
    planned: "PLANNED · 尚未执行",
    blocked: "BLOCKED · 无法执行",
  }[mode];
}

function structuredFailure(code: string): string {
  const messages: Record<string, string> = {
    STALE_BASE: "基线已变化，请创建新的评审版本并重新审批。",
    LOCK_CONFLICT: "二进制资产锁冲突，请查看锁所有者。",
    INCOMPATIBLE_SCHEMA: "输入合同不兼容，当前层不会显示为空差异。",
  };
  return messages[code] ?? `结构化错误：${code}`;
}

function state(
  surface: EditorSurfaceState,
  title: string,
  message: string,
  mode: ExecutionMode,
  retryCommandId: string | null,
): ReviewEditorView {
  return {
    state: surface,
    title,
    message,
    mode,
    modeLabel: modeLabel(mode),
    retryCommandId,
    conflictMessages: [],
  };
}
