import type {
  EditorPresentation,
  EditorStatus,
  ExecutionMode,
  RenderEditorLocalState,
} from "./contracts.ts";

const modeLabels: Record<ExecutionMode, string> = {
  live: "实时 LIVE",
  cached: "真实缓存 CACHED",
  mock: "确定性模拟 MOCK",
  planned: "待执行 PLANNED",
  blocked: "受阻 BLOCKED",
};

const stateLabels: Record<EditorStatus, string> = {
  loading: "正在加载",
  empty: "暂无内容",
  ready: "可审阅",
  failed: "执行失败",
  offline: "集成离线",
  "permission-denied": "权限不足",
};

export function executionModeLabel(mode: ExecutionMode): string {
  return modeLabels[mode];
}

export function buildPresentation(
  editorId: string,
  title: string,
  state: RenderEditorLocalState,
): EditorPresentation {
  const common = {
    editorId,
    title,
    stateLabel: stateLabels[state.status],
    modeLabel: modeLabels[state.executionMode],
    preservesServerQueue: true,
    sections: [] as EditorPresentation["sections"],
  };
  if (state.status === "loading") {
    return { ...common, tone: "info", message: "正在读取渲染数据…", actions: [] };
  }
  if (state.status === "empty") {
    return {
      ...common,
      tone: "neutral",
      message: "选择场景、固定相机和配方后创建渲染任务。",
      actions: [{ label: "创建任务", commandId: "render.recipe.run", input: {} }],
    };
  }
  if (state.status === "offline") {
    return {
      ...common,
      tone: "critical",
      message: "渲染集成未连接；不会把本地 fixture 标记为实时结果。",
      actions: [
        { label: "查看集成", commandId: "integration.open", input: { integrationId: "comfyui" } },
        { label: "重试", commandId: "render.job.retry", input: { jobId: state.selectedId } },
      ],
    };
  }
  if (state.status === "permission-denied") {
    return {
      ...common,
      tone: "warning",
      message: "缺少此操作所需的渲染权限。",
      actions: [{ label: "查看权限", commandId: "permission.explain", input: {} }],
    };
  }
  if (state.status === "failed") {
    return {
      ...common,
      tone: "critical",
      message: `渲染任务失败${state.errorCode ? `：${state.errorCode}` : ""}。日志和中间产物已保留。`,
      actions: [{ label: "重试任务", commandId: "render.job.retry", input: { jobId: state.selectedId } }],
    };
  }
  if (state.executionMode === "planned") {
    return {
      ...common,
      tone: "info",
      message: "渲染方案已规划，但尚未生成可审阅产物。",
      actions: [],
      sections: [],
    };
  }
  if (state.executionMode === "blocked") {
    return {
      ...common,
      tone: "critical",
      message: "渲染执行受阻；当前没有可声明为完成的产物。",
      actions: [{ label: "查看集成", commandId: "integration.open", input: {} }],
      sections: [],
    };
  }
  return {
    ...common,
    tone: state.executionMode === "mock" ? "warning" : "success",
    message: state.visible
      ? "结果已就绪，可检查 AOV、差异、审批和来源。"
      : "编辑器已隐藏；渲染队列由服务端继续持久化，前端轮询已暂停。",
    actions: [
      { label: "查看来源", commandId: "workbench.open_editor", input: { editorId: "render.provenance" } },
    ],
    sections: readySections(editorId, state),
  };
}

function readySections(
  editorId: string,
  state: RenderEditorLocalState,
): EditorPresentation["sections"] {
  const selected = state.selectedId ?? "未选择";
  if (editorId === "render.viewer") {
    return [
      {
        title: "变体审阅",
        rows: [
          { label: "变体", value: selected },
          { label: "审批", value: "等待人工确认" },
          { label: "约束", value: "Depth · Normal · Object ID" },
        ],
      },
    ];
  }
  if (editorId === "render.aov-viewer") {
    return [
      {
        title: "确定性通道",
        rows: [
          { label: "必需", value: "Beauty · Depth · Normal · Albedo · Object ID" },
          { label: "可选", value: "Material ID" },
          { label: "相机", value: "固定版本绑定" },
        ],
      },
    ];
  }
  if (editorId === "render.recipe") {
    return [
      {
        title: "可移植配方",
        rows: [
          { label: "资产", value: "Turntable · Material Variant" },
          { label: "场景", value: "Lighting/Visibility · Fixed Camera" },
          { label: "交付", value: "Marketing Still" },
        ],
      },
    ];
  }
  if (editorId === "render.queue") {
    return [
      {
        title: "任务状态",
        rows: [
          { label: "任务", value: selected },
          { label: "筛选", value: state.filter || "全部" },
          { label: "可恢复", value: "取消 · 重试 · 持久化" },
        ],
      },
    ];
  }
  if (editorId === "render.comparison") {
    return [
      {
        title: "固定相机证据",
        rows: [
          { label: "范围", value: "对象与属性 allowlist" },
          { label: "保护区", value: "阈值门禁" },
          { label: "结构", value: "几何与相机版本不变" },
        ],
      },
    ];
  }
  return [
    {
      title: "完整来源链",
      rows: [
        { label: "场景", value: "Scene · Camera · sceneops_id" },
        { label: "AI", value: "Workflow · Model · Seed · Prompt" },
        { label: "产物", value: "Output · SHA-256 · Approval" },
      ],
    },
  ];
}
