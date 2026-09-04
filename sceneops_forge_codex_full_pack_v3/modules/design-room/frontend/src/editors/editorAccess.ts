import type { ExecutionMode } from "../contracts.ts";

export interface DesignEditorAccess {
  readonly moduleEnabled: boolean;
  readonly hasReadPermission: boolean;
  readonly loading: boolean;
  readonly connected: boolean;
  readonly errorMessage: string | null;
}

export interface DesignEditorBlockedView {
  readonly state: "module-disabled" | "permission-denied" | "loading" | "disconnected" | "failed";
  readonly title: string;
  readonly message: string;
  readonly mode: ExecutionMode;
}

export function resolveDesignEditorBlock(access: DesignEditorAccess): DesignEditorBlockedView | null {
  if (!access.moduleEnabled) {
    return { state: "module-disabled", title: "Design Room 不可用", message: "模块已关闭，可在模块设置中启用。", mode: "blocked" };
  }
  if (!access.hasReadPermission) {
    return { state: "permission-denied", title: "无权查看设计文档", message: "需要 design:read 权限。", mode: "blocked" };
  }
  if (access.loading) {
    return { state: "loading", title: "正在加载设计文档", message: "正在读取结构化内容与版本…", mode: "planned" };
  }
  if (!access.connected) {
    return { state: "disconnected", title: "设计服务未连接", message: "保存不可用；检查服务连接后重试。", mode: "blocked" };
  }
  if (access.errorMessage !== null) {
    return { state: "failed", title: "设计文档加载失败", message: access.errorMessage, mode: "blocked" };
  }
  return null;
}
