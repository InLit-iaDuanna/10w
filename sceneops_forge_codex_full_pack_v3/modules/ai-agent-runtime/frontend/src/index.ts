import type { ModuleContribution } from "@sceneops/module-runtime";
import { generatedModuleManifest } from "./generated/module-manifest.ts";

export const moduleContribution = {
  manifest: generatedModuleManifest,
  editors: [],
} satisfies ModuleContribution;

export { AgentTaskWorkbench, AgentTaskActivity, AgentTaskTimeline,
  ProductionPreparationSummary } from './AgentTaskWorkbench';
export { agentTaskKeys, agentTasks } from './client';
export type { AgentTask } from './client';
export { ProductionModuleView, ProductionNodeStatus } from './ProductionModuleView';
export type { ProductionSelection } from './ProductionModuleView';
export { useProduction, productionApi, productionKeys } from './production-client';
export type { ProductionStep, ProductionArtifact, ProductionSnapshot } from './production-client';

export { DemoWorkbench } from './DemoWorkbench';

export { CardSourceEditor } from './CardSourceEditor';

export { ProjectGameTool, ProjectProgressTool } from './ProjectGameTools';
export { LaunchLatestGameButton } from './LaunchLatestGameButton';

export { ExperiencePanel } from './ExperiencePanel';
export { ExperienceReferences } from './ExperienceReferences';

export { LocalServerPanel } from './LocalServerPanel';

export { startProjectProduction } from './startProjectProduction';

export { MemoryMessage, MemoryActivity } from './MemoryActivity';

export {ProjectAssetWorkbench} from './ProjectAssetWorkbench';
export {ProjectProductionTool} from './ProjectProductionTool';
