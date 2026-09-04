import { createElement, type ReactElement } from "react";

import {
  buildEditorViewModel,
  type EditorSnapshot,
} from "../state/editor-state.ts";
import "./release-editor.css";

export interface ReleaseEditorFrameProps {
  editorId: string;
  title: string;
  description: string;
  snapshot: EditorSnapshot;
  onCommand?: (commandId: string) => void;
}

export default function ReleaseEditorFrame(
  props: ReleaseEditorFrameProps,
): ReactElement {
  const model = buildEditorViewModel(props.snapshot);
  const action = model.action;
  return createElement(
    "section",
    {
      className: "sceneops-release-editor",
      "data-editor-id": props.editorId,
      "data-view-state": props.snapshot.view,
      "data-execution-mode": props.snapshot.mode,
      "aria-label": props.title,
    },
    createElement(
      "header",
      { className: "sceneops-release-editor__header" },
      createElement("h2", null, props.title),
      createElement(
        "span",
        { className: `sceneops-release-mode sceneops-release-mode--${props.snapshot.mode}` },
        model.modeLabel,
      ),
    ),
    createElement("p", { className: "sceneops-release-editor__description" }, props.description),
    createElement(
      "div",
      { className: "sceneops-release-editor__state", role: props.snapshot.view === "failed" ? "alert" : "status" },
      createElement("strong", null, model.headline),
      createElement("span", null, model.stateLabel),
      model.detail ? createElement("p", null, model.detail) : null,
    ),
    action
      ? createElement(
          "div",
          { className: "sceneops-release-editor__action" },
          createElement(
            "button",
            {
              type: "button",
              disabled: action.disabled,
              title: action.reason,
              onClick: () => props.onCommand?.(action.commandId),
            },
            action.label,
          ),
          action.reason ? createElement("span", null, action.reason) : null,
        )
      : null,
  );
}
