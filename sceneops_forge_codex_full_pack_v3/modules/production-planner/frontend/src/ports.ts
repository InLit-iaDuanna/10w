import type {
  CreatePlanCommandRequest,
  CreatePlanCommandResponse,
} from "./generated/contracts.ts";

export interface ProductionPlannerApi {
  createPlan(request: CreatePlanCommandRequest): Promise<CreatePlanCommandResponse>;
}

export interface WorkbenchCommandPort {
  dispatch(commandId: string, input: unknown): Promise<unknown>;
}
