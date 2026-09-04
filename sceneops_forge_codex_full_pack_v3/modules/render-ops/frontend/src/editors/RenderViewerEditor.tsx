import * as React from "react";
import type { RenderEditorProps } from "../contracts.ts";
import { buildPresentation } from "../presentation.ts";
import { EditorFrame } from "./EditorFrame.tsx";

export default function RenderViewerEditor(props: RenderEditorProps) {
  return React.createElement(EditorFrame, {
    presentation: buildPresentation("render.viewer", "渲染查看器", props.localState),
    props,
  });
}
