import type {
  CreatePlanCommandRequest,
  CreatePlanCommandResponse,
  PlannerErrorResponse,
} from "../generated/contracts.ts";
import type { ProductionPlannerApi } from "../ports.ts";

export interface CreatePlanCommandContext {
  api: ProductionPlannerApi;
  permissions: ReadonlySet<string>;
  moduleEnabled: boolean;
}

export type CreatePlanCommandResult =
  | {
      status: "succeeded";
      response: CreatePlanCommandResponse;
      openPlanAction: {
        commandId: "workbench.open_editor";
        input: Record<string, unknown>;
      };
    }
  | { status: "unavailable"; code: string; message: string }
  | { status: "failed"; error: PlannerErrorResponse };

function isPlannerError(value: unknown): value is PlannerErrorResponse {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.code === "string" && typeof candidate.message === "string";
}

async function executeCreateProductionPlan(
  context: CreatePlanCommandContext,
  input: CreatePlanCommandRequest,
): Promise<CreatePlanCommandResult> {
  if (!context.moduleEnabled) {
    return { status: "unavailable", code: "MODULE_DISABLED", message: "生产计划模块已停用。" };
  }
  if (!context.permissions.has("production-plan:write")) {
    return { status: "unavailable", code: "PERMISSION_DENIED", message: "没有创建生产计划的权限。" };
  }
  try {
    const response = await context.api.createPlan(input);
    return {
      status: "succeeded",
      response,
      openPlanAction: {
        commandId: "workbench.open_editor",
        input: {
          editorId: "production.plan",
          placement: { mode: "split", direction: "right" },
          context: {
            activeFeatureId: response.plan.feature_id,
            activeTaskId: null,
            productionPlanId: response.plan.plan_id,
          },
          requireConfirmation: true,
        },
      },
    };
  } catch (error) {
    if (isPlannerError(error)) return { status: "failed", error };
    return {
      status: "failed",
      error: {
        code: "PLANNER_DISCONNECTED",
        message: "无法连接生产计划服务。",
        details: {},
        request_id: "request:unassigned",
        retryable: true,
        suggested_actions: ["integration.retry"],
      },
    };
  }
}

export const createProductionPlanCommand = {
  id: "production.plan.create",
  title: "创建生产计划",
  chatAliases: ["/创建生产计划", "/production-plan"],
  requiredPermissions: ["production-plan:write"],
  execute: executeCreateProductionPlan,
} as const;

export const invokeCreatePlanFromChat = executeCreateProductionPlan;
export const invokeCreatePlanFromButton = executeCreateProductionPlan;
