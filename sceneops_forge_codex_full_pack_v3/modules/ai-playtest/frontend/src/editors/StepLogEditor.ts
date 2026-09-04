import { createElement } from "react";
import { EditorSurface } from "./EditorSurface.ts";
import type { PlaytestEditorProps } from "../types.ts";
import { stepLogViewModel } from "../view-models.ts";

export default function StepLogEditor(props: PlaytestEditorProps) {
  const rows = stepLogViewModel(props.readModel);
  return createElement(
    EditorSurface,
    { ...props, title: "步骤日志" },
    createElement(
      "table",
      null,
      createElement(
        "thead",
        null,
        createElement(
          "tr",
          null,
          ...["步骤", "时间", "动作", "目标", "结果", "信号", "观测/证据"].map((label) =>
            createElement("th", { key: label, scope: "col" }, label),
          ),
        ),
      ),
      createElement(
        "tbody",
        null,
        ...rows.map((row) =>
          createElement(
            "tr",
            { key: row.stepIndex },
            createElement(
              "td",
              null,
              createElement(
                "button",
                {
                  type: "button",
                  onClick: () => props.updateLocalState({ selectedStepIndex: row.stepIndex }),
                },
                String(row.stepIndex),
              ),
            ),
            createElement("td", null, row.occurredAt),
            createElement("td", null, row.action),
            createElement("td", null, row.target),
            createElement("td", null, row.outcome),
            createElement("td", null, row.signals),
            createElement(
              "td",
              null,
              createElement(
                "details",
                null,
                createElement(
                  "summary",
                  null,
                  `${row.availableActionIds.length} 动作 · ${row.evidenceArtifactIds.length} 工件`,
                ),
                createElement("pre", null, JSON.stringify({
                  camera: row.camera,
                  gameState: row.gameState,
                  goals: row.goals,
                  availableActionIds: row.availableActionIds,
                  evidenceArtifactIds: row.evidenceArtifactIds,
                }, null, 2)),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}
