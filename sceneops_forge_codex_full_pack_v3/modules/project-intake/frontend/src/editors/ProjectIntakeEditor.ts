import type {
  ExecutionMode,
  IntakeFieldKey,
  ProjectIntakeRecord,
} from "../contracts.ts";
import type { ProjectScanHealth } from "../adapters/ProjectScanAdapter.ts";
import { listFieldsByConfidence, validateIntakeForActivation } from "../validation.ts";

export interface ProjectIntakeEditorInput {
  readonly moduleEnabled: boolean;
  readonly hasReadPermission: boolean;
  readonly loading: boolean;
  readonly integrationHealth: ProjectScanHealth | null;
  readonly record: ProjectIntakeRecord | null;
  readonly errorMessage: string | null;
}

export interface ProjectIntakeEditorView {
  readonly state:
    | "module-disabled"
    | "permission-denied"
    | "loading"
    | "integration-offline"
    | "failed"
    | "empty"
    | "ready";
  readonly title: string;
  readonly message: string;
  readonly mode: ExecutionMode;
  readonly inferredFields: readonly IntakeFieldKey[];
  readonly missingFields: readonly IntakeFieldKey[];
  readonly validationMessages: readonly string[];
}

function blocked(
  state: ProjectIntakeEditorView["state"],
  title: string,
  message: string,
): ProjectIntakeEditorView {
  return {
    state,
    title,
    message,
    mode: "blocked",
    inferredFields: [],
    missingFields: [],
    validationMessages: [],
  };
}

export default function buildProjectIntakeEditorView(
  input: ProjectIntakeEditorInput,
): ProjectIntakeEditorView {
  if (!input.moduleEnabled) return blocked("module-disabled", "项目入口不可用", "Project Intake 模块已关闭。可在模块设置中启用。");
  if (!input.hasReadPermission) return blocked("permission-denied", "无权查看项目入口", "需要 project:read 权限。");
  if (input.loading) {
    return { ...blocked("loading", "正在加载项目入口", "正在读取结构化项目字段…"), mode: "planned" };
  }
  if (input.integrationHealth?.status === "offline") {
    return blocked("integration-offline", "扫描集成已离线", input.integrationHealth.message);
  }
  if (input.integrationHealth?.status === "permission-denied") {
    return blocked("permission-denied", "扫描目录无权限", input.integrationHealth.message);
  }
  if (input.errorMessage !== null) return blocked("failed", "项目入口加载失败", input.errorMessage);
  if (input.record === null) {
    return { ...blocked("empty", "尚无项目入口", "从对话创建新项目，或选择一个现有项目根目录。"), mode: "planned" };
  }
  return {
    state: "ready",
    title: input.record.fields.projectName.value ?? "未命名项目",
    message: input.record.status === "ready" ? "关键项目设置已确认。" : "请确认推断字段并补齐缺失字段。",
    mode: input.record.mode,
    inferredFields: listFieldsByConfidence(input.record, "inferred"),
    missingFields: listFieldsByConfidence(input.record, "missing"),
    validationMessages: validateIntakeForActivation(input.record).map((issue) => issue.message),
  };
}
