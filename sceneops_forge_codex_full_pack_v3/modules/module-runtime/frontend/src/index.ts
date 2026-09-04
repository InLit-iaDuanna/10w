import { generatedModuleManifest } from "./generated/module-manifest.ts";

export type {
  ModuleAvailability,
  ModuleContribution,
  ModuleManifest,
  ModuleRuntimeState,
  ModuleStatus,
} from "./manifest.ts";
export { resolveFrontendModuleStates } from "./manifest.ts";

export const moduleContribution = {
  manifest: generatedModuleManifest,
  editors: [],
  commands: ["module.catalog.inspect"],
  events: ["module.catalog.generated@1"],
  jobs: ["module.catalog.build"],
} as const;
