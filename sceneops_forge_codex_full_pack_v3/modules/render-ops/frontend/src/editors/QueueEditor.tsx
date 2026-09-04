import * as React from "react";
import type { RenderEditorProps } from "../contracts.ts";
import { buildPresentation } from "../presentation.ts";
import { EditorFrame } from "./EditorFrame.tsx";

export default function QueueEditor(props: RenderEditorProps) {
  return React.createElement(EditorFrame, {
    presentation: buildPresentation("render.queue", "渲染队列", props.localState),
    props,
  });
}
