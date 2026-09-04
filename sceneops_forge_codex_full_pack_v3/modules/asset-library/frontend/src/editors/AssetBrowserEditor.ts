import { createElement, type ReactElement } from "react";

import type { AssetEditorState } from "../models.ts";

export interface AssetBrowserEditorProps {
  state: AssetEditorState;
  onRetry: () => void;
  onOpenIntegration: () => void;
  onSelectAsset: (assetId: string) => void;
}

export default function AssetBrowserEditor(props: AssetBrowserEditorProps): ReactElement {
  const { state } = props;
  if (state.kind === "failed") {
    return createElement("section", { role: "alert" }, [
      createElement("p", { key: "label" }, state.label),
      createElement("button", { key: "retry", onClick: props.onRetry }, state.action),
    ]);
  }
  if (state.kind === "disconnected") {
    return createElement("section", { role: "status" }, [
      createElement("p", { key: "label" }, state.label),
      createElement(
        "button",
        { key: "integration", onClick: props.onOpenIntegration },
        state.action,
      ),
    ]);
  }
  if (state.kind !== "ready") {
    return createElement("p", { role: "status" }, state.label);
  }
  return createElement("section", { "aria-label": "资产浏览器" }, [
    createElement("p", { key: "count" }, state.label),
    createElement(
      "ul",
      { key: "assets" },
      state.assets.map((asset) =>
        createElement("li", { key: asset.assetId },
          createElement(
            "button",
            { onClick: () => props.onSelectAsset(asset.assetId) },
            `${asset.displayName} · ${asset.triangleCount ?? "未处理"} tris · ${asset.executionMode}`,
          ),
        ),
      ),
    ),
  ]);
}
