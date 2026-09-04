import { createElement, type ReactElement } from "react";

import ReleaseEditorFrame from "../components/ReleaseEditorFrame.tsx";
import { plannedSnapshot } from "../state/editor-state.ts";
import type { BuildReleaseEditorComponentProps } from "./editor-component.ts";

export default function BuildConsoleEditor(
  props: BuildReleaseEditorComponentProps,
): ReactElement {
  return createElement(ReleaseEditorFrame, {
    editorId: "build.console",
    title: "构建控制台",
    description: "查看构建尝试、结构化日志、取消、失败原因与可重试状态。",
    snapshot: props.snapshot ?? plannedSnapshot("构建控制台"),
    onCommand: props.onCommand,
  });
}
