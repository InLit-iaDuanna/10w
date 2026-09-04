import type { ProductionPlan, ProductionTask } from "../generated/contracts.ts";
import type { WorkbenchCommandPort } from "../ports.ts";

export async function openTaskInRecommendedEditor(
  commands: WorkbenchCommandPort,
  plan: ProductionPlan,
  task: ProductionTask,
): Promise<unknown> {
  return commands.dispatch("workbench.open_editor", {
    editorId: task.recommended_editor_id,
    placement: { mode: "tab" },
    context: {
      projectId: plan.project_id,
      activeFeatureId: plan.feature_id,
      activeTaskId: task.task_id,
      productionPlanId: plan.plan_id,
    },
    requireConfirmation: true,
  });
}

export const openProductionTaskCommand = {
  id: "production.task.open",
  title: "在相关工具中打开任务",
  requiredPermissions: ["production-plan:read"],
  execute: openTaskInRecommendedEditor,
} as const;
