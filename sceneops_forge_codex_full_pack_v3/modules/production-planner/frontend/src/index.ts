import { createProductionPlanCommand } from "./commands/createProductionPlan.ts";
import { openProductionTaskCommand } from "./commands/openTask.ts";
import {
  manifest,
  plannedProductionPlanEditor,
  plannedProductionTaskEditor,
} from "./manifest.ts";

export const moduleContribution = {
  manifest,
  editors: [],
  commands: [],
  eventHandlers: [],
  navigation: [],
} as const;

export const blockedFrontendContributions = {
  reason: manifest.blockedReason,
  editors: [plannedProductionPlanEditor, plannedProductionTaskEditor],
  commands: [createProductionPlanCommand, openProductionTaskCommand],
  navigation: [
    {
      editorId: "production.plan",
      group: "项目",
      keywords: ["计划", "任务", "依赖", "里程碑", "关键路径"],
      recommendedEdges: ["left", "right"],
    },
  ],
} as const;

export { createProductionPlanCommand } from "./commands/createProductionPlan.ts";
export { openProductionTaskCommand, openTaskInRecommendedEditor } from "./commands/openTask.ts";
export {
  modeLabel,
  productionPlanDocument,
  restorePlannerState,
  serializePlannerState,
} from "./editors/editorState.ts";
export type { ProductionPlannerApi, WorkbenchCommandPort } from "./ports.ts";
export type {
  CreatePlanCommandRequest,
  CreatePlanCommandResponse,
  ProductionGraphView,
  ProductionPlan,
  ProductionTask,
} from "./generated/contracts.ts";
