import type {
  LogicEditorDefinition,
  LogicEditorState,
  LogicEditorStatus,
  LogicEditorView,
} from "./editorTypes.ts";

const STATUS_LABELS: Record<LogicEditorStatus, string> = {
  loading: "加载中",
  empty: "空",
  ready: "就绪",
  failed: "失败",
  offline: "未连接",
  permission_denied: "无权限",
};

const runtime = {
  createView(
    definition: LogicEditorDefinition,
    state: LogicEditorState,
  ): LogicEditorView {
    const common = {
      editorId: definition.id,
      title: definition.title,
      status: state.status,
      statusLabel: STATUS_LABELS[state.status],
      modeLabel: state.mode.toUpperCase(),
    };
    if (state.status === "loading") {
      return {
        ...common,
        tone: "neutral",
        message: "正在加载逻辑数据…",
        actions: [],
      };
    }
    if (state.status === "empty") {
      return {
        ...common,
        tone: "neutral",
        message: definition.emptyMessage,
        actions: [],
      };
    }
    if (state.status === "failed") {
      return {
        ...common,
        tone: "critical",
        message: `逻辑数据加载失败（${state.errorCode ?? "UNKNOWN"}）。`,
        actions: [{ id: "retry", label: "重试" }],
      };
    }
    if (state.status === "offline") {
      return {
        ...common,
        tone: "warning",
        message: "Unity 未连接；图编辑仍可用，编译与 Play Mode 测试不可用。",
        actions: [{ id: "open_integration", label: "打开集成中心" }],
      };
    }
    if (state.status === "permission_denied") {
      return {
        ...common,
        tone: "warning",
        message: "当前用户缺少打开此逻辑工具所需的权限。",
        actions: [{ id: "request_permission", label: "查看所需权限" }],
      };
    }
    return {
      ...common,
      tone: "success",
      message: "逻辑图已加载，可检查、比较和生成测试。",
      actions: [],
    };
  },
};

export default runtime;
