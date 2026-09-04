import type {
  ConceptEditorLocalState,
  EditorAvailability,
  MoodboardPresentation,
  StyleBiblePresentation,
} from "../types.ts";

export interface EditorAccessInput {
  moduleEnabled: boolean;
  hasReadPermission: boolean;
  loading: boolean;
  errorMessage?: string;
  conceptId?: string | null;
}

export function resolveEditorAvailability(input: EditorAccessInput): EditorAvailability {
  if (!input.moduleEnabled) {
    return { kind: "disabled", message: "Concept Lab 已由功能开关停用。" };
  }
  if (!input.hasReadPermission) {
    return { kind: "permission", message: "缺少 concept:read 权限。" };
  }
  if (input.loading) {
    return { kind: "loading" };
  }
  if (input.errorMessage) {
    return {
      kind: "failed",
      message: input.errorMessage,
      retryCommandId: "concept.open",
    };
  }
  if (!input.conceptId) {
    return { kind: "empty", message: "选择任务或从对话创建概念后开始。" };
  }
  return { kind: "ready" };
}

export function generationOfflineAvailability(reason: string): EditorAvailability {
  return {
    kind: "offline",
    message: `图像生成不可用：${reason}`,
    importCommandId: "concept.reference.import",
  };
}

export function defaultConceptEditorState(): ConceptEditorLocalState {
  return { selectedVariantIds: [], showRejected: true, pinnedConceptId: null };
}

export function serializeConceptEditorState(state: ConceptEditorLocalState): unknown {
  return {
    selectedVariantIds: [...state.selectedVariantIds],
    showRejected: state.showRejected,
    pinnedConceptId: state.pinnedConceptId,
  };
}

export function restoreConceptEditorState(value: unknown): ConceptEditorLocalState {
  if (!value || typeof value !== "object") {
    return defaultConceptEditorState();
  }
  const candidate = value as Record<string, unknown>;
  return {
    selectedVariantIds: Array.isArray(candidate.selectedVariantIds)
      ? candidate.selectedVariantIds.filter((item): item is string => typeof item === "string")
      : [],
    showRejected:
      typeof candidate.showRejected === "boolean" ? candidate.showRejected : true,
    pinnedConceptId:
      typeof candidate.pinnedConceptId === "string" ? candidate.pinnedConceptId : null,
  };
}

export function moodboardNotice(presentation: MoodboardPresentation): string | null {
  if (presentation.executionMode === "mock") return "MOCK · 确定性示例，不是实时生成";
  if (presentation.executionMode === "cached") return "CACHED · 复用既有运行记录";
  if (presentation.executionMode === "planned") return "PLANNED · 尚未执行";
  if (presentation.executionMode === "blocked") return "BLOCKED · 查看原因或导入参考图";
  return presentation.notice;
}

export function styleAssessmentText(value: StyleBiblePresentation): string {
  if (value.latestAssessment === null) return "尚未检查";
  const label = {
    consistent: "证据支持一致",
    needs_review: "需要人工复核",
    inconsistent: "存在不一致证据",
  }[value.latestAssessment];
  const confidence = value.confidence === null ? "未提供" : `${Math.round(value.confidence * 100)}%`;
  return `${label} · 证据置信度 ${confidence}`;
}
