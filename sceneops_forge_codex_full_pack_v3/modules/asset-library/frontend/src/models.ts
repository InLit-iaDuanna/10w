export type ExecutionMode = "live" | "cached" | "mock" | "planned" | "blocked";
export type GateStatus = "passed" | "failed" | "warning" | "not_run";
export type UnityStatus =
  | "not_imported"
  | "pending"
  | "imported"
  | "failed"
  | "unavailable";

export interface AssetSummary {
  assetId: string;
  assetVersionId: string | null;
  assetVersionNumber: number | null;
  displayName: string;
  category: string;
  sourcePath: string;
  sourceKind: "imported" | "generated" | "scanned";
  sourceVersion: string;
  formats: string[];
  dimensionsM: { x: number; y: number; z: number } | null;
  triangleCount: number | null;
  materialCount: number | null;
  textureCount: number | null;
  hasUv: boolean | null;
  isRigged: boolean | null;
  animationNames: string[];
  lodCount: number | null;
  colliderKind: string | null;
  licenseName: string;
  hasAiProvenance: boolean;
  aiProvenanceProviders: string[];
  sceneIds: string[];
  unityStatus: UnityStatus;
  buildIds: string[];
  gateStatuses: GateStatus[];
  executionMode: ExecutionMode;
}

export interface AssetBrowserFilter {
  query: string;
  formats: string[];
  gateStatus?: GateStatus;
  unityStatus?: UnityStatus;
  hasUv?: boolean;
  rigged?: boolean;
  hasAnimations?: boolean;
  hasLod?: boolean;
  hasCollider?: boolean;
  hasAiProvenance?: boolean;
  licenseName?: string;
  minTriangles?: number;
  maxTriangles?: number;
  executionModes: ExecutionMode[];
}

export type AssetEditorState =
  | { kind: "loading"; label: "正在加载资产…" }
  | { kind: "empty"; label: "没有符合条件的资产" }
  | { kind: "permission"; label: "没有查看资产的权限" }
  | { kind: "disconnected"; label: "资产服务未连接"; action: "打开集成中心" }
  | { kind: "failed"; label: string; action: "重试" }
  | { kind: "ready"; label: string; assets: AssetSummary[]; modeLabels: ExecutionMode[] };

export interface AssetQuerySnapshot {
  loading: boolean;
  permissionGranted: boolean;
  connected: boolean;
  error?: { code: string; message: string };
  assets: AssetSummary[];
}
