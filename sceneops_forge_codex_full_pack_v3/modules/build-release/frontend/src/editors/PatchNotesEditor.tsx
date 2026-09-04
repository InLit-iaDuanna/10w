import { createElement, type ReactElement } from "react";

import ReleaseEditorFrame from "../components/ReleaseEditorFrame.tsx";
import { plannedSnapshot } from "../state/editor-state.ts";
import type { BuildReleaseEditorComponentProps } from "./editor-component.ts";

export default function PatchNotesEditor(
  props: BuildReleaseEditorComponentProps,
): ReactElement {
  return createElement(ReleaseEditorFrame, {
    editorId: "release.patch-notes",
    title: "补丁说明",
    description: "仅从候选中已批准的 ChangeSet 生成条目，并保留人工编辑修订历史。",
    snapshot: props.snapshot ?? plannedSnapshot("补丁说明"),
    onCommand: props.onCommand,
  });
}
