import {
  EditorRegistry,
  type EditorDefinition,
} from '../../../../modules/forge-shell/frontend/src/index.ts';

export interface FrontendModuleContribution {
  manifest: { id: string; featureFlag?: string };
  editors?: readonly EditorDefinition[];
}

export function createEditorRegistry(
  contributions: readonly FrontendModuleContribution[],
  enabledModuleIds: ReadonlySet<string>,
): EditorRegistry {
  const registry = new EditorRegistry();
  for (const contribution of contributions) {
    if (!enabledModuleIds.has(contribution.manifest.id)) continue;
    registry.registerAll(contribution.editors ?? []);
  }
  return registry;
}

export { EditorRegistry };
