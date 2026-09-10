import type { EditorDefinition } from "@sceneops/core-ui";
import type { ModuleContribution } from "@sceneops/module-runtime";
import { generatedModuleManifest } from "./generated/module-manifest.ts";

export const pipelineEditor = {
  id: "harness.pipeline",
  title: "AI 生产计划",
  icon: "workflow",
  category: "AI 制作",
  defaultPlacement: { mode: "split", direction: "right" },
  singleton: true,
  renderPolicy: "suspend-when-hidden",
  load: () => import("./PipelineWorkbench").then(module => ({ default: module.PipelineWorkbench })),
  initialState: () => null,
  serializeState: () => null,
  restoreState: () => null,
} satisfies EditorDefinition<null>;

export const moduleContribution = {
  manifest: generatedModuleManifest,
  editors: [pipelineEditor],
} satisfies ModuleContribution;

export { PipelineWorkbench } from './PipelineWorkbench';
export { harness, harnessKeys } from './client';
export type { Proposal, Run, PlanRequest } from './client';
export const loadPipelineWorkbench = () => import('./PipelineWorkbench').then(module => ({default: module.PipelineWorkbench}));
