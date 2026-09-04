import type { WorkbenchContextSummary } from "../conversation/types.ts";

export interface ContextChip {
  id: string;
  label: string;
  value: string;
}

export function buildContextChips(
  context: WorkbenchContextSummary,
): ContextChip[] {
  const chips: ContextChip[] = [];
  if (context.projectId) {
    chips.push({
      id: `project:${context.projectId}`,
      label: "项目",
      value: context.projectName ?? context.projectId,
    });
  }
  if (context.sceneId) {
    chips.push({
      id: `scene:${context.sceneId}`,
      label: "场景",
      value: context.sceneName ?? context.sceneId,
    });
  }
  if (context.selectedSceneObjectIds.length > 0) {
    chips.push({
      id: "selection",
      label: "对象",
      value: `${context.selectedSceneObjectIds.length} 个`,
    });
  }
  if (context.activeFeatureId) {
    chips.push({ id: "feature", label: "功能", value: context.activeFeatureId });
  }
  if (context.activeBuildId) {
    chips.push({ id: "build", label: "构建", value: context.activeBuildId });
  }
  if (context.activeIssueId) {
    chips.push({ id: "issue", label: "问题", value: context.activeIssueId });
  }
  return chips;
}
