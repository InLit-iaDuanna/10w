import { commandDefinitions } from "./commands/definitions.ts";
import { editorDefinitions } from "./editors/definitions.ts";
import { manifest } from "./manifest.ts";

export const moduleContribution = {
  manifest,
  editors: editorDefinitions,
  commands: commandDefinitions,
} as const;

export { UnityBuildWorkbench } from './workbench/UnityBuildWorkbench';
export const loadIntegratedWorkbench = () => import('./IntegratedWorkbench');
export { ExportWorkbench } from './export/ExportWorkbench';
export type { ExportWorkbenchProps } from './export/ExportWorkbench';
export const loadExportWorkbench = () => import('./export/ExportWorkbench');
