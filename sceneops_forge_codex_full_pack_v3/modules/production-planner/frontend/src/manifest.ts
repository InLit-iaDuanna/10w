export const manifest = {
  id: "production-planner",
  version: "0.1.0",
  featureFlag: "production_planner",
  requiredModules: ["core-kernel", "module-runtime", "design-room"],
  frontendIntegrationStatus: "blocked",
  blockedReason: "React, module-runtime, and core command/editor contracts are unavailable.",
} as const;

export const plannedProductionPlanEditor = {
  id: "production.plan",
  title: "生产计划",
  integrationStatus: "blocked",
  reason: "A React EditorDefinition cannot be registered before the shared editor contract exists.",
} as const;

export const plannedProductionTaskEditor = {
  id: "production.task",
  title: "生产任务",
  integrationStatus: "blocked",
  reason: "A React EditorDefinition cannot be registered before the shared editor contract exists.",
} as const;
