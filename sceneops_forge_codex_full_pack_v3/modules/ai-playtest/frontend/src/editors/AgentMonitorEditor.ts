import { createElement } from "react";
import { EditorSurface } from "./EditorSurface.ts";
import type { PlaytestEditorProps } from "../types.ts";
import { agentMonitorViewModel } from "../view-models.ts";

export default function AgentMonitorEditor(props: PlaytestEditorProps) {
  const view = agentMonitorViewModel(props.readModel);
  const controls = props.readModel.surfaceState !== "ready"
    ? null
    : view.status === "running"
    ? createElement(
        "button",
        {
          type: "button",
          onClick: () => props.commands.execute("playtest.cancel", { runId: view.runId }),
        },
        "取消运行",
      )
    : createElement(
        "button",
        {
          type: "button",
          disabled: props.retryInput === undefined,
          onClick: () => props.commands.execute("playtest.run", props.retryInput),
        },
        "运行 TestCase",
      );
  return createElement(
    EditorSurface,
    { ...props, title: "代理监控" },
    createElement(
      "div",
      null,
      createElement("p", null, view.objective ?? "尚未选择 TestCase。"),
      createElement(
        "p",
        null,
        `${view.status ?? "未运行"} · 目标 ${view.completedGoals}/${view.goalCount}`,
      ),
      createElement("p", null, `当前动作：${view.currentAction ?? "—"}`),
      createElement(
        "p",
        null,
        `模式：${view.agentMode ?? "—"} · 边界：${view.actionBounds?.maxSteps ?? "—"} 步 / ${view.actionBounds?.maxDurationMs ?? "—"} ms / 单步 ${view.actionBounds?.actionTimeoutMs ?? "—"} ms`,
      ),
      createElement(
        "ul",
        null,
        ...view.goals.map((goal) =>
          createElement(
            "li",
            { key: goal.goalId },
            `${goal.label} · ${goal.state} · ${Math.round(goal.value * 100)}%`,
          ),
        ),
      ),
      controls,
    ),
  );
}
