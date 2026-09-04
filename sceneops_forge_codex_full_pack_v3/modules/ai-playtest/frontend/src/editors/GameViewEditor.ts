import { createElement } from "react";
import { EditorSurface } from "./EditorSurface.ts";
import type { PlaytestEditorProps } from "../types.ts";
import { gameViewModel } from "../view-models.ts";

export default function GameViewEditor(props: PlaytestEditorProps) {
  const view = gameViewModel(props.readModel);
  const camera = view.camera
    ? `相机 ${view.camera.position.join(", ")} · 旋转 ${view.camera.rotationEulerDegrees.join(", ")}`
    : "无相机证据";
  return createElement(
    EditorSurface,
    { ...props, title: "游戏画面" },
    createElement(
      "figure",
      null,
      view.screenshotUri
        ? createElement("img", {
            src: view.screenshotUri,
            alt: `Playtest ${props.readModel.runId ?? "未命名"} 截图`,
          })
        : createElement("p", null, "当前运行没有截图工件。"),
      createElement("figcaption", null, `${view.buildId ?? "无构建"} · ${camera}`),
    ),
  );
}
