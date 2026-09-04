import { createElement } from "react";
import { EditorSurface } from "./EditorSurface.ts";
import type { PlaytestEditorProps } from "../types.ts";
import { regressionViewModel } from "../view-models.ts";

export default function RegressionEditor(props: PlaytestEditorProps) {
  const view = regressionViewModel(props.readModel);
  const canCompare = Boolean(
    props.localState.comparisonId
    && props.localState.baselineRunId
    && props.localState.candidateRunId,
  );
  return createElement(
    EditorSurface,
    { ...props, title: "回归比较" },
    createElement(
      "div",
      null,
      createElement("p", null, `比较结果：${view.status ?? "尚未比较"}`),
      createElement(
        "p",
        null,
        `精确配置：${view.exactConfiguration === true ? "是" : "否/未验证"} · ${view.baselineBuildId ?? "—"} → ${view.candidateBuildId ?? "—"}`,
      ),
      createElement("p", null, `改善 ${view.improved} · 退化 ${view.regressed}`),
      createElement(
        "p",
        null,
        `问题：新增 ${view.newIssueIds.length} · 已解决 ${view.resolvedIssueIds.length} · 持续 ${view.persistentIssueIds.length}`,
      ),
      createElement(
        "ul",
        null,
        ...view.metrics.map((metric) =>
          createElement(
            "li",
            { key: metric.metricId },
            `${metric.metricId}: ${metric.baseline ?? "—"} → ${metric.candidate ?? "—"} ${metric.unit} · ${metric.outcome}`,
          ),
        ),
      ),
      createElement(
        "button",
        {
          type: "button",
          disabled: !canCompare,
          onClick: () => props.commands.execute("playtest.regression.compare", {
            comparisonId: props.localState.comparisonId,
            baselineRunId: props.localState.baselineRunId,
            candidateRunId: props.localState.candidateRunId,
          }),
        },
        "按精确配置比较",
      ),
    ),
  );
}
