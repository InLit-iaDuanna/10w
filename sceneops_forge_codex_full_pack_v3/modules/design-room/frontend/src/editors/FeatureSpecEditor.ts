import type { ExecutionMode, FeatureSpec } from "../contracts.ts";
import { validateFeatureSpec } from "../validation.ts";
import type { DesignEditorAccess, DesignEditorBlockedView } from "./editorAccess.ts";
import { resolveDesignEditorBlock } from "./editorAccess.ts";

export interface FeatureSpecEditorView {
  readonly state: "empty" | "ready" | "needs-attention";
  readonly title: string;
  readonly message: string;
  readonly mode: ExecutionMode;
  readonly validationMessages: readonly string[];
  readonly deliverablesByKind: Readonly<Record<string, number>>;
}

export default function buildFeatureSpecEditorView(
  access: DesignEditorAccess,
  spec: FeatureSpec | null,
  mode: ExecutionMode,
): FeatureSpecEditorView | DesignEditorBlockedView {
  const blocked = resolveDesignEditorBlock(access);
  if (blocked !== null) return blocked;
  if (spec === null) {
    return { state: "empty", title: "尚无 Feature Spec", message: "从对话创建结构化功能草稿。", mode: "planned", validationMessages: [], deliverablesByKind: {} };
  }
  const issues = validateFeatureSpec(spec);
  const deliverablesByKind = Object.fromEntries(
    ["asset", "scene", "script", "ui", "audio", "vfx"].map((kind) => [
      kind,
      spec.requiredDeliverables.filter((item) => item.kind === kind).length,
    ]),
  );
  return {
    state: issues.length === 0 ? "ready" : "needs-attention",
    title: spec.title,
    message: issues.length === 0 ? "功能规格可以进入准备度检查。" : `还有 ${issues.length} 项需要处理。`,
    mode,
    validationMessages: issues.map((issue) => issue.message),
    deliverablesByKind,
  };
}
