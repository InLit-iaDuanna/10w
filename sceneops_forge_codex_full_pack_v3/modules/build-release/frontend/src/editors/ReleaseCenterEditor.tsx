import { createElement, type ReactElement } from "react";

import ReleaseEditorFrame from "../components/ReleaseEditorFrame.tsx";
import { plannedSnapshot } from "../state/editor-state.ts";
import type { BuildReleaseEditorComponentProps } from "./editor-component.ts";

export default function ReleaseCenterEditor(
  props: BuildReleaseEditorComponentProps,
): ReactElement {
  return createElement(ReleaseEditorFrame, {
    editorId: "release.center",
    title: "发布中心",
    description: "审查候选、精确审批、部署历史、已知良好版本与回滚计划。",
    snapshot: props.snapshot ?? plannedSnapshot("发布中心"),
    onCommand: props.onCommand,
  });
}
