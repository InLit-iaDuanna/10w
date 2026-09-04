import { createElement } from "react";
import { EditorSurface } from "./EditorSurface.ts";
import type { PlaytestEditorProps } from "../types.ts";
import { trajectoryViewModel } from "../view-models.ts";

export default function TrajectoryEditor(props: PlaytestEditorProps) {
  const points = trajectoryViewModel(props.readModel);
  return createElement(
    EditorSurface,
    { ...props, title: "轨迹" },
    createElement(
      "ol",
      { "aria-label": "Playtest 轨迹点" },
      ...points.map((point) =>
        createElement(
          "li",
          { key: point.stepIndex },
          createElement(
            "button",
            {
              type: "button",
              onClick: () => props.updateLocalState({
                selectedStepIndex: point.stepIndex,
              }),
            },
            `#${point.stepIndex} · (${point.position.join(", ")}) · ${point.outcome}`,
          ),
        ),
      ),
    ),
  );
}
