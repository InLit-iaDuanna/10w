import { createElement } from "react";
import type { ReactNode } from "react";

import { editorStatus } from "../editor-state.ts";
import type { PlaytestEditorProps } from "../types.ts";

export interface EditorSurfaceProps extends PlaytestEditorProps {
  title: string;
  children?: ReactNode;
}

export function EditorSurface(props: EditorSurfaceProps) {
  const { executionMode, surfaceState } = props.readModel;
  const status = editorStatus(surfaceState, executionMode);
  const children: ReactNode[] = [
    createElement(
      "header",
      { key: "header" },
      createElement("h2", null, props.title),
      createElement(
        "span",
        { "data-execution-mode": executionMode },
        status.modeLabel,
      ),
      createElement(
        "button",
        { type: "button", onClick: props.close, "aria-label": `关闭${props.title}` },
        "关闭",
      ),
    ),
    createElement(
      "p",
      { key: "state", role: status.isFailure ? "alert" : "status" },
      status.stateLabel,
    ),
  ];
  if (props.readModel.summary) {
    children.push(createElement("p", { key: "summary" }, props.readModel.summary));
  }
  if (props.readModel.errorMessage) {
    children.push(createElement("pre", { key: "error" }, props.readModel.errorMessage));
  }
  if (surfaceState === "failed") {
    children.push(
      createElement(
        "button",
        {
          key: "retry",
          type: "button",
          disabled: props.retryInput === undefined,
          onClick: () => props.commands.execute("playtest.run", props.retryInput),
        },
        "重试",
      ),
    );
  }
  if (props.children && (surfaceState === "ready" || surfaceState === "failed")) {
    children.push(props.children);
  }
  if (props.readModel.limitationLabels.length > 0) {
    children.push(
      createElement(
        "aside",
        { key: "limitations", "aria-label": "AI Playtest 限制" },
        createElement("strong", null, "限制"),
        createElement(
          "ul",
          null,
          ...props.readModel.limitationLabels.map((label) =>
            createElement("li", { key: label }, label),
          ),
        ),
      ),
    );
  }
  return createElement(
    "section",
    {
      "data-editor-state": surfaceState,
      "data-context-binding": props.contextBinding.mode,
      "data-editor-instance": props.instanceId,
    },
    ...children,
  );
}
