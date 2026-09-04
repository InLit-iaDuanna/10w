import { generatedModuleManifest } from "./generated/module-manifest.ts";

export interface KernelFailureState {
  readonly status: "failed";
  readonly mode: "mock" | "live" | "cached" | "blocked" | "planned";
  readonly code: string;
  readonly message: string;
}

export function describeKernelFailure(
  code: string,
  message: string,
  mode: KernelFailureState["mode"],
): KernelFailureState {
  return { status: "failed", mode, code, message };
}

export const moduleContribution = {
  manifest: generatedModuleManifest,
  editors: [],
  commands: ["core.run.transition"],
  events: ["core.run.state_changed@1"],
  jobs: ["core.run.transition"],
} as const;
