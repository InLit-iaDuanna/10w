import type {
  ExecutionMode,
  SerializedUnityEditorState,
  UnityEditorState,
} from "./types.ts";

export const executionModeLabels: Readonly<Record<ExecutionMode, string>> = {
  live: "实时",
  cached: "缓存实跑",
  mock: "确定性模拟",
  planned: "仅计划",
  blocked: "已阻塞",
};

export const defaultSerializedUnityEditorState: SerializedUnityEditorState = {
  schemaVersion: 1,
  selectedBuildId: null,
  selectedSceneOpsId: null,
  followGlobalContext: true,
  logLevel: "info",
};

export function serializeUnityEditorState(
  state: SerializedUnityEditorState,
): SerializedUnityEditorState {
  return { ...state, schemaVersion: 1 };
}
export function restoreUnityEditorState(value: unknown): SerializedUnityEditorState {
  if (!isRecord(value) || value.schemaVersion !== 1) {
    return { ...defaultSerializedUnityEditorState };
  }
  const logLevel = value.logLevel;
  return {
    schemaVersion: 1,
    selectedBuildId: asNullableString(value.selectedBuildId),
    selectedSceneOpsId: asNullableString(value.selectedSceneOpsId),
    followGlobalContext:
      typeof value.followGlobalContext === "boolean" ? value.followGlobalContext : true,
    logLevel:
      logLevel === "warning" || logLevel === "error" ? logLevel : "info",
  };
}

export function integrationState(
  mode: ExecutionMode,
  input: {
    loading?: boolean;
    enabled?: boolean;
    permitted?: boolean;
    connected?: boolean;
    hasSelection?: boolean;
    failure?: { code: string; message: string; retryable: boolean };
  },
): UnityEditorState {
  if (input.enabled === false) {
    return {
      kind: "offline",
      mode: "blocked",
      title: "Unity 模块已停用",
      message: "请先启用 engine_unity 功能标志。",
    };
  }
  if (input.permitted === false) {
    return {
      kind: "permission-denied",
      mode: "blocked",
      title: "没有 Unity 权限",
      message: "当前账号无权读取或执行 Unity 操作。",
    };
  }
  if (input.loading) {
    return { kind: "loading", mode, title: "正在连接 Unity", message: "正在读取集成状态…" };
  }
  if (input.connected === false) {
    return {
      kind: "offline",
      mode: "blocked",
      title: "Unity 未连接",
      message: "检查 Editor 路径、项目根目录和 SceneOps Unity Package。",
      retryCommandId: "unity.health",
    };
  }
  if (input.failure) {
    return {
      kind: "failed",
      mode,
      title: "Unity 操作失败",
      message: `${input.failure.code}：${input.failure.message}`,
      retryCommandId: input.failure.retryable ? "run.retry" : undefined,
      details: input.failure,
    };
  }
  if (input.hasSelection === false) {
    return {
      kind: "empty",
      mode,
      title: "未选择 Unity 对象",
      message: "从场景、Prefab 或构建记录中选择一个稳定 ID。",
    };
  }
  return {
    kind: "ready",
    mode,
    title: `Unity · ${executionModeLabels[mode]}`,
    message: "集成已就绪。",
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asNullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}
