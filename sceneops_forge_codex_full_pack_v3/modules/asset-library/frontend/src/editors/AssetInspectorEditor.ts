import { createElement, type ReactElement } from "react";

import type { AssetSummary } from "../models.ts";

export interface AssetInspectorEditorProps {
  asset: AssetSummary | null;
}

export default function AssetInspectorEditor({ asset }: AssetInspectorEditorProps): ReactElement {
  if (!asset) {
    return createElement("p", { role: "status" }, "选择一个资产以查看来源、版本和使用位置");
  }
  const rows = [
    ["执行模式", asset.executionMode],
    ["来源", `${asset.sourceKind} · ${asset.sourcePath} · ${asset.sourceVersion}`],
    ["资产版本", asset.assetVersionNumber ? `v${asset.assetVersionNumber} · ${asset.assetVersionId}` : "未发布"],
    ["格式", asset.formats.join(", ") || "未发布"],
    [
      "尺寸（米）",
      asset.dimensionsM
        ? `${asset.dimensionsM.x} × ${asset.dimensionsM.y} × ${asset.dimensionsM.z}`
        : "未处理",
    ],
    ["三角面", String(asset.triangleCount ?? "未处理")],
    ["材质 / 贴图", `${asset.materialCount ?? 0} / ${asset.textureCount ?? 0}`],
    ["UV / 骨骼 / 动画", `${asset.hasUv ? "有" : "无"} / ${asset.isRigged ? "有" : "无"} / ${asset.animationNames.length}`],
    ["LOD / 碰撞体", `${asset.lodCount ?? 0} / ${asset.colliderKind ?? "无"}`],
    ["许可证", asset.licenseName],
    [
      "AI 来源",
      asset.hasAiProvenance
        ? asset.aiProvenanceProviders.join(", ") || "有（查看来源记录）"
        : "无",
    ],
    ["场景", asset.sceneIds.join(", ") || "未使用"],
    ["Unity", asset.unityStatus],
    ["构建", asset.buildIds.join(", ") || "未包含"],
  ];
  return createElement(
    "dl",
    { "aria-label": `${asset.displayName} 资产检查器` },
    rows.flatMap(([term, value]) => [
      createElement("dt", { key: `${term}-term` }, term),
      createElement("dd", { key: `${term}-value` }, value),
    ]),
  );
}
