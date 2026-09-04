import type {
  CreatePlanCommandResponse,
  ExecutionMode,
  ProductionTask,
} from "../generated/contracts.ts";

export type PlannerContextBinding =
  | { mode: "follow-global" }
  | { mode: "pinned"; projectId: string; featureId: string; planId: string };

export interface PlannerEditorLocalState {
  selectedTaskId: string | null;
  zoom: number;
  panX: number;
  panY: number;
  contextBinding: PlannerContextBinding;
}

export type PlannerEditorState =
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "module_disabled" }
  | { kind: "permission_denied" }
  | { kind: "disconnected"; retryable: boolean }
  | { kind: "failed"; code: string; message: string; retryable: boolean }
  | { kind: "ready"; data: CreatePlanCommandResponse };

export interface EditorDocument {
  heading: string;
  statusLabel: string;
  modeLabel?: string;
  sourceModeLabel?: string;
  message: string;
  actions: string[];
  criticalPathTaskIds: string[];
  blockerMessages: string[];
  milestoneRows: Array<{
    milestoneId: string;
    state: string;
    incompleteTaskIds: string[];
  }>;
  taskRows: Array<{
    taskId: string;
    title: string;
    assignment: string;
    estimate: string;
    status: string;
    blocked: boolean;
  }>;
}

export function modeLabel(mode: ExecutionMode): string {
  return {
    live: "LIVE · 当前执行",
    cached: "CACHED · 既有真实运行",
    mock: "MOCK · 确定性示例",
    planned: "PLANNED · 尚未执行",
    blocked: "BLOCKED · 无法执行",
  }[mode];
}

function unavailableDocument(state: Exclude<PlannerEditorState, { kind: "ready" }>): EditorDocument {
  const content = {
    loading: ["正在加载生产计划…", []],
    empty: ["还没有生产计划。可从对话中执行“创建生产计划”。", ["production.plan.create"]],
    module_disabled: ["生产计划模块已停用。", []],
    permission_denied: ["没有查看生产计划的权限。", []],
    disconnected: ["生产计划服务未连接。", state.kind === "disconnected" && state.retryable ? ["integration.retry"] : []],
    failed: [state.kind === "failed" ? `${state.message}（${state.code}）` : "生产计划加载失败。", state.kind === "failed" && state.retryable ? ["run.retry"] : []],
  }[state.kind] as [string, string[]];
  return {
    heading: "生产计划",
    statusLabel: state.kind,
    message: content[0],
    actions: content[1],
    criticalPathTaskIds: [],
    blockerMessages: [],
    milestoneRows: [],
    taskRows: [],
  };
}

function taskRow(task: ProductionTask, graphBlocked: boolean) {
  const measured = [...(task.estimates ?? [])].reverse().find((estimate) => estimate.kind === "measured");
  const estimate = measured ?? task.estimates[0];
  return {
    taskId: task.task_id,
    title: task.title,
    assignment: `${task.assignment.kind === "human" ? "人工" : "代理"} · ${task.assignment.display_name}`,
    estimate: `${estimate.kind === "measured" ? "实测" : "预测"} ${estimate.hours}h`,
    status: task.status ?? "draft",
    blocked: graphBlocked || (task.blockers?.length ?? 0) > 0,
  };
}

export function productionPlanDocument(state: PlannerEditorState): EditorDocument {
  if (state.kind !== "ready") return unavailableDocument(state);
  const { plan, graph } = state.data;
  const graphNodes = new Map(graph.nodes.map((node) => [node.task_id, node]));
  return {
    heading: plan.feature_title,
    statusLabel: plan.status,
    modeLabel: modeLabel(plan.execution_mode),
    sourceModeLabel: `Feature Spec：${modeLabel(plan.feature_source_mode)}`,
    message: `关键路径 ${graph.critical_path.total_hours}h · ${graph.blockers.length} 个阻断项`,
    actions: plan.status === "draft_unconfirmed" ? ["production.plan.approval.open"] : [],
    criticalPathTaskIds: graph.critical_path.task_ids,
    blockerMessages: graph.blockers.map((blocker) => blocker.message),
    milestoneRows: graph.milestone_readiness.map((milestone) => ({
      milestoneId: milestone.milestone_id,
      state: milestone.state,
      incompleteTaskIds: milestone.incomplete_task_ids,
    })),
    taskRows: plan.tasks.map((task) => taskRow(task, graphNodes.get(task.task_id)?.blocked ?? false)),
  };
}

export function serializePlannerState(state: PlannerEditorLocalState): string {
  return JSON.stringify(state);
}

export function restorePlannerState(serialized: string): PlannerEditorLocalState {
  const parsed = JSON.parse(serialized) as PlannerEditorLocalState;
  if (!parsed.contextBinding || typeof parsed.zoom !== "number") {
    throw new Error("INVALID_PLANNER_EDITOR_STATE");
  }
  return parsed;
}
