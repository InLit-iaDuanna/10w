import * as React from "react";
import type { RenderEditorProps } from "../contracts.ts";
import { buildPresentation } from "../presentation.ts";
import { EditorFrame } from "./EditorFrame.tsx";

export default function ProvenanceEditor(props: RenderEditorProps) {
  const presentation = buildPresentation("render.provenance", "渲染来源", props.localState);
  presentation.disclaimer = "场景、相机、对象、配方、工作流、模型、种子、提示词、输出校验和与审批必须完整。";
  return React.createElement(EditorFrame, { presentation, props });
}
