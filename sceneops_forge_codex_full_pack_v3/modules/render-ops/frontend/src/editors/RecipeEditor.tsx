import * as React from "react";
import type { RenderEditorProps } from "../contracts.ts";
import { buildPresentation } from "../presentation.ts";
import { EditorFrame } from "./EditorFrame.tsx";

export default function RecipeEditor(props: RenderEditorProps) {
  return React.createElement(EditorFrame, {
    presentation: buildPresentation("render.recipe", "渲染配方", props.localState),
    props,
  });
}
