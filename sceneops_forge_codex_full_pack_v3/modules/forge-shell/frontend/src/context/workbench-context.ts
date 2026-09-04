import type { ContextBinding, EditorInstance, WorkbenchContext } from '../contracts.ts';
import type { WorkbenchEventBus } from '../events/workbench-event-bus.ts';

export const EMPTY_WORKBENCH_CONTEXT: WorkbenchContext = {
  projectId: null,
  branchId: null,
  sceneId: null,
  selectedSceneObjectIds: [],
  selectedAssetIds: [],
  activeFeatureId: null,
  activeTaskId: null,
  activeChangeSetId: null,
  activeRenderJobId: null,
  activeBuildId: null,
  activePlaytestRunId: null,
  activeIssueId: null,
};

export function resolveContext(globalContext: WorkbenchContext, binding: ContextBinding): WorkbenchContext {
  if (binding.mode === 'follow-global') return cloneContext(globalContext);
  return { ...cloneContext(globalContext), ...cloneContextPatch(binding.context) };
}

export function setContextBinding(
  instance: EditorInstance,
  binding: ContextBinding,
  events: WorkbenchEventBus,
): EditorInstance {
  const updated = { ...instance, contextBinding: structuredClone(binding) };
  events.emit('workbench.context.binding_changed@1', {
    instanceId: instance.instanceId,
    binding: updated.contextBinding,
  });
  return updated;
}

function cloneContext(context: WorkbenchContext): WorkbenchContext {
  return structuredClone(context);
}
function cloneContextPatch(context: Partial<WorkbenchContext>): Partial<WorkbenchContext> {
  return structuredClone(context);
}
