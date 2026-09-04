import { readFile } from "node:fs/promises";

import type {
  CreatePlanCommandRequest,
  CreatePlanCommandResponse,
} from "../generated/contracts.ts";

export async function keyDoorResponse(): Promise<CreatePlanCommandResponse> {
  const fixtureUrl = new URL(
    "../../../contracts/examples/key-door-production-plan.mock.json",
    import.meta.url,
  );
  return JSON.parse(await readFile(fixtureUrl, "utf8")) as CreatePlanCommandResponse;
}

export function keyDoorRequest(): CreatePlanCommandRequest {
  return {
    feature_ref: {
      project_id: "project:remember-home",
      feature_id: "feature:key-and-door",
      revision: 1,
    },
  };
}
