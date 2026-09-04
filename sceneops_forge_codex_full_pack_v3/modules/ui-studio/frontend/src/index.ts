/** Public frontend entrypoint. No engine SDK or engine-unity internals are imported here. */
import { manifest } from "./manifest";
import { uiCommands, uiCommandSchemas, uiModuleAvailability } from "./commands/uiCommands";
import { uiFlowEditor } from "./editors/uiFlowEditor";
import { uiPreviewEditor } from "./editors/uiPreviewEditor";

export { manifest, uiCommands, uiCommandSchemas, uiFlowEditor, uiPreviewEditor, uiModuleAvailability };
export const uiStudioKeys = { all: ["ui-studio"] as const, flow: (id: string) => ["ui-studio", "flow", id] as const };
export const moduleContribution = { manifest, editors: [uiFlowEditor, uiPreviewEditor], commands: uiCommands };
export { UiLabPanel } from './editors/UiLabPanel';
export type { paths as UiLabPaths, components as UiLabComponents } from './lab-api';
