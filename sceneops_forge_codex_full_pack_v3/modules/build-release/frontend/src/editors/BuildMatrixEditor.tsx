import { createElement, type ReactElement } from "react";

import ReleaseEditorFrame from "../components/ReleaseEditorFrame.tsx";
import { plannedSnapshot } from "../state/editor-state.ts";
import type { BuildReleaseEditorComponentProps } from "./editor-component.ts";

export default function BuildMatrixEditor(
  props: BuildReleaseEditorComponentProps,
): ReactElement {
  return createElement(ReleaseEditorFrame, {
    editorId: "build.matrix",
    title: "构建矩阵",
    description: "比较 Development、QA、Judge 与 Release Candidate 配置，并固定 A/B 输入。",
    snapshot: props.snapshot ?? plannedSnapshot("构建矩阵"),
    onCommand: props.onCommand,
  });
}
