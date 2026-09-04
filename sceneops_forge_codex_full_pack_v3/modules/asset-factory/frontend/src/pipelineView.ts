export type ExecutionMode = "live" | "cached" | "mock" | "planned" | "blocked";
export type PipelineState =
  | "queued"
  | "planning"
  | "planned"
  | "waiting_approval"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "timed_out"
  | "rolled_back"
  | "blocked";

export interface PipelineStepSummary {
  stepId: string;
  label: string;
  state: string;
  progress: number;
  attempts: number;
  skipReason?: string;
  errorCode?: string;
}

export interface PipelineSnapshot {
  loading: boolean;
  permissionGranted: boolean;
  integrationConnected: boolean;
  run: {
    pipelineRunId: string;
    state: PipelineState;
    executionMode: ExecutionMode;
    steps: PipelineStepSummary[];
    errorMessage?: string;
  } | null;
  error?: { code: string; message: string; retryable: boolean };
}

export type PipelineEditorState =
  | { kind: "loading"; message: "正在加载资产流水线…" }
  | { kind: "permission"; message: "没有运行资产流水线的权限" }
  | { kind: "disconnected"; message: "Blender 未连接"; action: "打开集成中心" }
  | { kind: "empty"; message: "选择 AssetSpec 以开始预检" }
  | { kind: "failed"; message: string; retryable: boolean; action?: "重试" }
  | {
      kind: "approval";
      message: "变更集等待审批";
      action: "查看并审批";
      mode: "planned";
      steps: PipelineStepSummary[];
    }
  | {
      kind: "ready";
      message: string;
      mode: ExecutionMode;
      steps: PipelineStepSummary[];
      canCancel: boolean;
      canRetry: boolean;
      canRollback: boolean;
    };

export function buildPipelineEditorState(snapshot: PipelineSnapshot): PipelineEditorState {
  if (!snapshot.permissionGranted) {
    return { kind: "permission", message: "没有运行资产流水线的权限" };
  }
  if (!snapshot.integrationConnected) {
    return { kind: "disconnected", message: "Blender 未连接", action: "打开集成中心" };
  }
  if (snapshot.loading) {
    return { kind: "loading", message: "正在加载资产流水线…" };
  }
  if (snapshot.error) {
    return {
      kind: "failed",
      message: snapshot.error.message,
      retryable: snapshot.error.retryable,
      action: snapshot.error.retryable ? "重试" : undefined,
    };
  }
  if (!snapshot.run) {
    return { kind: "empty", message: "选择 AssetSpec 以开始预检" };
  }
  if (snapshot.run.state === "waiting_approval") {
    return {
      kind: "approval",
      message: "变更集等待审批",
      action: "查看并审批",
      mode: "planned",
      steps: snapshot.run.steps,
    };
  }
  const retryableStates: PipelineState[] = ["failed", "cancelled", "timed_out", "rolled_back", "blocked"];
  return {
    kind: "ready",
    message: snapshot.run.errorMessage ?? stateLabel(snapshot.run.state),
    mode: snapshot.run.executionMode,
    steps: snapshot.run.steps,
    canCancel: snapshot.run.state === "running",
    canRetry: retryableStates.includes(snapshot.run.state),
    canRollback:
      snapshot.run.state !== "succeeded" &&
      snapshot.run.steps.some((step) => step.label === "snapshot" && step.state === "succeeded"),
  };
}

function stateLabel(state: PipelineState): string {
  const labels: Record<PipelineState, string> = {
    queued: "排队中",
    planning: "正在生成预览",
    planned: "预演完成，未执行",
    waiting_approval: "变更集等待审批",
    running: "正在处理资产",
    succeeded: "资产版本已发布",
    failed: "资产流水线失败",
    cancelled: "资产流水线已取消",
    timed_out: "资产流水线超时",
    rolled_back: "失败后已回滚快照",
    blocked: "资产流水线被阻止",
  };
  return labels[state];
}
