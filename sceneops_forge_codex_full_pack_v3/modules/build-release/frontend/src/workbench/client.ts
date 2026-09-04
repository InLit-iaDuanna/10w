import createClient from "openapi-fetch";
import type { paths, components } from "./api.generated";
export type Snapshot = components["schemas"]["WorkbenchSnapshot"];
export type Scenario = components["schemas"]["BuildScenario"];
export type ProposalInput = components["schemas"]["ProposalInput"];
export type ChangeSet = components["schemas"]["ChangeSet"];

function unwrap<T>(result: { data?: T; error?: unknown }): T {
  if (result.error || !result.data)
    throw new Error(
      typeof result.error === "object"
        ? JSON.stringify(result.error)
        : String(result.error || "API 未返回数据"),
    );
  return result.data;
}
export const workbenchKeys = { snapshot: ["unity-build", "snapshot"] as const };
export function createUnityBuildClient(fetchImpl: typeof fetch = fetch) {
const client = createClient<paths>({ fetch: fetchImpl });
return {
  snapshot: async () => unwrap(await client.GET("/api/unity-build/snapshot")),
  save: async (slug: string, body: ProposalInput) =>
    unwrap(
      await client.PUT("/api/unity-build/proposals/{slug}", {
        params: { path: { slug } },
        body,
      }),
    ),
  preview: async (body: ChangeSet) =>
    unwrap(await client.POST("/api/unity-build/preview", { body })),
};
}
export const workbenchApi = createUnityBuildClient();
