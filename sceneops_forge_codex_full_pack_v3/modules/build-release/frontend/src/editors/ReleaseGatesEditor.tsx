import { createElement, type ReactElement } from "react";

import ReleaseEditorFrame from "../components/ReleaseEditorFrame.tsx";
import { plannedSnapshot } from "../state/editor-state.ts";
import type { BuildReleaseEditorComponentProps } from "./editor-component.ts";

export default function ReleaseGatesEditor(
  props: BuildReleaseEditorComponentProps,
): ReactElement {
  return createElement(ReleaseEditorFrame, {
    editorId: "release.gates",
    title: "发布门禁",
    description: "聚合资产、场景、代码、渲染、Unity 测试、性能与 AI 回归证据。",
    snapshot: props.snapshot ?? plannedSnapshot("发布门禁"),
    onCommand: props.onCommand,
  });
}
