import * as React from "react";

import type { EditorPresentation, RenderEditorProps } from "../contracts.ts";

export function EditorFrame({
  presentation,
  props,
}: {
  presentation: EditorPresentation;
  props: RenderEditorProps;
}) {
  return React.createElement(
    "section",
    {
      "aria-label": presentation.title,
      "data-editor-id": presentation.editorId,
      "data-mode": props.localState.executionMode,
      "data-state": props.localState.status,
    },
    React.createElement("header", null,
      React.createElement("h2", null, presentation.title),
      React.createElement("span", null, presentation.stateLabel),
      React.createElement("span", null, presentation.modeLabel),
    ),
    React.createElement("p", { role: presentation.tone === "critical" ? "alert" : "status" }, presentation.message),
    presentation.disclaimer
      ? React.createElement("p", { "data-kind": "disclaimer" }, presentation.disclaimer)
      : null,
    ...presentation.sections.map((section) =>
      React.createElement(
        "section",
        { key: section.title, "aria-label": section.title },
        React.createElement("h3", null, section.title),
        React.createElement(
          "dl",
          null,
          ...section.rows.flatMap((row) => [
            React.createElement("dt", { key: `${section.title}:${row.label}:label` }, row.label),
            React.createElement("dd", { key: `${section.title}:${row.label}:value` }, row.value),
          ]),
        ),
      ),
    ),
    React.createElement(
      "div",
      null,
      ...presentation.actions.map((action) =>
        React.createElement(
          "button",
          {
            key: action.label,
            type: "button",
            onClick: () => props.commands.execute(action.commandId, action.input),
          },
          action.label,
        ),
      ),
    ),
  );
}
