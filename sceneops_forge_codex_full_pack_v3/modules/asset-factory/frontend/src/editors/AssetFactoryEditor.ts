import { createElement, type ReactElement } from "react";

import type { PipelineEditorState } from "../pipelineView.ts";

export interface AssetFactoryEditorProps {
  state: PipelineEditorState;
  onRetry: () => void;
  onCancel: () => void;
  onRollback: () => void;
  onOpenApproval: () => void;
  onOpenIntegration: () => void;
}

export default function AssetFactoryEditor(props: AssetFactoryEditorProps): ReactElement {
  const state = props.state;
  if (state.kind === "disconnected") {
    return createElement("section", { role: "status" }, [
      createElement("p", { key: "message" }, state.message),
      createElement("button", { key: "action", onClick: props.onOpenIntegration }, state.action),
    ]);
  }
  if (state.kind === "approval") {
    return createElement("section", { role: "status", "data-mode": state.mode }, [
      createElement("p", { key: "message" }, `${state.message} · PLANNED`),
      createElement("button", { key: "action", onClick: props.onOpenApproval }, state.action),
    ]);
  }
  if (state.kind !== "ready") {
    const retry = state.kind === "failed" && state.action
      ? createElement("button", { key: "retry", onClick: props.onRetry }, state.action)
      : null;
    return createElement("section", { role: state.kind === "failed" ? "alert" : "status" }, [
      createElement("p", { key: "message" }, state.message),
      retry,
    ]);
  }
  const actions = [
    state.canCancel && createElement("button", { key: "cancel", onClick: props.onCancel }, "取消"),
    state.canRetry && createElement("button", { key: "retry", onClick: props.onRetry }, "重试"),
    state.canRollback && createElement("button", { key: "rollback", onClick: props.onRollback }, "回滚快照"),
  ].filter(Boolean);
  return createElement("section", { "aria-label": "资产工厂", "data-mode": state.mode }, [
    createElement("p", { key: "status" }, `${state.message} · ${state.mode.toUpperCase()}`),
    createElement(
      "ol",
      { key: "steps" },
      state.steps.map((step) =>
        createElement(
          "li",
          { key: step.stepId },
          `${step.label} · ${step.state} · ${Math.round(step.progress * 100)}% · ${step.attempts} 次`,
        ),
      ),
    ),
    createElement("div", { key: "actions" }, actions),
  ]);
}
