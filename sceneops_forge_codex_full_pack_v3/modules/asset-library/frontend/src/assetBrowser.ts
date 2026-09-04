import type {
  AssetBrowserFilter,
  AssetEditorState,
  AssetQuerySnapshot,
  AssetSummary,
} from "./models.ts";

export const emptyAssetFilter: AssetBrowserFilter = {
  query: "",
  formats: [],
  executionModes: [],
};

export function filterAssets(
  assets: readonly AssetSummary[],
  filter: AssetBrowserFilter,
): AssetSummary[] {
  const query = filter.query.trim().toLocaleLowerCase("zh-CN");
  return assets
    .filter((asset) => {
      const searchable = [
        asset.displayName,
        asset.category,
        asset.sourcePath,
        asset.sourceVersion,
        asset.licenseName,
        ...asset.aiProvenanceProviders,
        ...asset.sceneIds,
        ...asset.buildIds,
      ]
        .join(" ")
        .toLocaleLowerCase("zh-CN");
      const checks: boolean[] = [
        !query || searchable.includes(query),
        !filter.formats.length ||
          filter.formats.every((format) =>
            asset.formats.some((candidate) => candidate.toLowerCase() === format.toLowerCase()),
          ),
        !filter.gateStatus || asset.gateStatuses.includes(filter.gateStatus),
        !filter.unityStatus || asset.unityStatus === filter.unityStatus,
        filter.hasUv === undefined || asset.hasUv === filter.hasUv,
        filter.rigged === undefined || asset.isRigged === filter.rigged,
        filter.hasAnimations === undefined ||
          Boolean(asset.animationNames.length) === filter.hasAnimations,
        filter.hasLod === undefined || Boolean(asset.lodCount && asset.lodCount > 0) === filter.hasLod,
        filter.hasCollider === undefined || Boolean(asset.colliderKind) === filter.hasCollider,
        filter.hasAiProvenance === undefined ||
          asset.hasAiProvenance === filter.hasAiProvenance,
        !filter.licenseName || asset.licenseName === filter.licenseName,
        filter.minTriangles === undefined ||
          (asset.triangleCount !== null && asset.triangleCount >= filter.minTriangles),
        filter.maxTriangles === undefined ||
          (asset.triangleCount !== null && asset.triangleCount <= filter.maxTriangles),
        !filter.executionModes.length || filter.executionModes.includes(asset.executionMode),
      ];
      return checks.every(Boolean);
    })
    .sort((left, right) => left.displayName.localeCompare(right.displayName, "zh-CN"));
}

export function buildAssetEditorState(
  snapshot: AssetQuerySnapshot,
  filter: AssetBrowserFilter,
): AssetEditorState {
  if (!snapshot.permissionGranted) {
    return { kind: "permission", label: "没有查看资产的权限" };
  }
  if (!snapshot.connected) {
    return { kind: "disconnected", label: "资产服务未连接", action: "打开集成中心" };
  }
  if (snapshot.loading) {
    return { kind: "loading", label: "正在加载资产…" };
  }
  if (snapshot.error) {
    return { kind: "failed", label: snapshot.error.message, action: "重试" };
  }
  const assets = filterAssets(snapshot.assets, filter);
  if (!assets.length) {
    return { kind: "empty", label: "没有符合条件的资产" };
  }
  return {
    kind: "ready",
    label: `${assets.length} 个资产`,
    assets,
    modeLabels: [...new Set(assets.map((asset) => asset.executionMode))],
  };
}

export const assetKeys = {
  all: ["assets"] as const,
  list: (projectId: string, filter: AssetBrowserFilter) =>
    [...assetKeys.all, "list", projectId, filter] as const,
  detail: (assetId: string) => [...assetKeys.all, "detail", assetId] as const,
};
