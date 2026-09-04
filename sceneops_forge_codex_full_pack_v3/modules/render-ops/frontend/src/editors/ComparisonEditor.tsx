import * as React from "react";
import type { RenderEditorProps } from "../contracts.ts";
import { buildPresentation } from "../presentation.ts";
import { EditorFrame } from "./EditorFrame.tsx";

export default function ComparisonEditor(props: RenderEditorProps) {
  const presentation = buildPresentation("render.comparison", "渲染对比", props.localState);
  presentation.disclaimer = "像素差异只证明画面发生变化，不评价艺术质量。";
  return React.createElement(EditorFrame, { presentation, props });
}
