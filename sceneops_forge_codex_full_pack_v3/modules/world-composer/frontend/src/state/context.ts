import type {
  WorldContextBinding,
  WorldContextProjection,
} from '../issue-restoration.ts';

export function resolveWorldContext(
  binding: WorldContextBinding,
  globalContext: WorldContextProjection,
): WorldContextProjection {
  if (binding.mode === 'follow-global') return structuredClone(globalContext);
  return {
    ...structuredClone(globalContext),
    ...structuredClone(binding.context),
    selectedSceneObjectIds:
      binding.context.selectedSceneObjectIds === undefined
        ? [...globalContext.selectedSceneObjectIds]
        : [...binding.context.selectedSceneObjectIds],
  };
}

export function pinWorldContext(
  context: WorldContextProjection,
): WorldContextBinding {
  return { mode: 'pinned', context: structuredClone(context) };
}
