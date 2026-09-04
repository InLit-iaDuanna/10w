import type {
  CommandExecutionContext,
  EditorPlacement,
  WorkbenchCommandDefinition,
} from '../contracts.ts';
import type { WorkspaceCoordinator } from '../state/workspace-coordinator.ts';

export function createShellCommandDefinitions(
  coordinator: WorkspaceCoordinator,
): WorkbenchCommandDefinition<unknown, unknown>[] {
  return [
    command('workbench.open_editor', '打开编辑器', isOpenInput, async (input, context) =>
      coordinator.openEditor({
        editorId: input.editorId,
        source: context.source,
        ...(input.placement === undefined ? {} : { placement: structuredClone(input.placement) }),
        ...(context.source === 'assistant' || input.confirmed === undefined
          ? {}
          : { confirmed: input.confirmed }),
        ...(context.source === 'assistant' || input.forceReplaceDirty === undefined
          ? {}
          : { forceReplaceDirty: input.forceReplaceDirty }),
      }),
    ),
    command('workbench.close_editor', '关闭编辑器', isInstanceInput, async (input, context) =>
      coordinator.closeEditor(input.instanceId, {
        source: context.source,
        confirmed: context.source !== 'assistant' && input.confirmed === true,
      }),
    ),
    command('workbench.reopen_editor', '重新打开编辑器', isEmptyInput, async (_input, context) =>
      coordinator.reopenEditor(context.source),
    ),
    command('workbench.move_editor', '移动编辑器', isMoveInput, async (input, context) => {
      const result = await coordinator.moveEditor(input.instanceId, structuredClone(input.placement), {
        source: context.source,
        confirmed: context.source !== 'assistant' && input.confirmed === true,
        forceReplaceDirty: context.source !== 'assistant' && input.forceReplaceDirty === true,
      });
      return result.status === 'completed' ? { status: 'moved' } : result;
    }),
    command('workbench.switch_editor', '切换编辑器类型', isSwitchInput, async (input, context) =>
      coordinator.switchEditor(input.instanceId, input.editorId, {
        source: context.source,
        confirmed: context.source !== 'assistant' && input.confirmed === true,
      }),
    ),
    command('workspace.undo_layout', '撤销布局操作', isEmptyInput, async (_input, context) => {
      if (context.source === 'assistant' && coordinator.isCustomized()) {
        return { status: 'confirmation-required', reason: 'assistant-layout-change' };
      }
      return { status: (await coordinator.undo()) ? 'undone' : 'empty' };
    }),
    command('workspace.reset', '重置工作区', isResetInput, async (input, context) => {
      const result = await coordinator.reset(input.presetId, {
        source: context.source,
        confirmed: context.source !== 'assistant' && input.confirmed === true,
      });
      return result.status === 'completed' ? { status: 'reset' } : result;
    }),
  ];
}

function command<TInput, TResult>(
  id: string,
  title: string,
  validate: (value: unknown) => value is TInput,
  execute: (input: TInput, context: CommandExecutionContext) => Promise<TResult>,
): WorkbenchCommandDefinition<TInput, TResult> {
  return {
    id,
    title,
    requiredPermissions: ['workbench:write'],
    validate,
    canExecute: () => ({ available: true }),
    execute: (context, input) => execute(input, context),
  };
}

interface OpenInput {
  editorId: string;
  placement?: EditorPlacement;
  confirmed?: boolean;
  forceReplaceDirty?: boolean;
}

interface InstanceInput {
  instanceId: string;
  confirmed?: boolean;
}

interface MoveInput {
  instanceId: string;
  placement: EditorPlacement;
  confirmed?: boolean;
  forceReplaceDirty?: boolean;
}

interface SwitchInput {
  instanceId: string;
  editorId: string;
  confirmed?: boolean;
}

function isOpenInput(value: unknown): value is OpenInput {
  return isRecord(value) &&
    hasOnlyKeys(value, ['editorId', 'placement', 'confirmed', 'forceReplaceDirty']) &&
    typeof value.editorId === 'string' && value.editorId.length > 0 &&
    (value.placement === undefined || isEditorPlacement(value.placement)) &&
    optionalBoolean(value.confirmed) &&
    optionalBoolean(value.forceReplaceDirty);
}

function isInstanceInput(value: unknown): value is InstanceInput {
  return isRecord(value) &&
    hasOnlyKeys(value, ['instanceId', 'confirmed']) &&
    typeof value.instanceId === 'string' && value.instanceId.length > 0 &&
    optionalBoolean(value.confirmed);
}

function isMoveInput(value: unknown): value is MoveInput {
  return isRecord(value) &&
    hasOnlyKeys(value, ['instanceId', 'placement', 'confirmed', 'forceReplaceDirty']) &&
    typeof value.instanceId === 'string' && value.instanceId.length > 0 &&
    isEditorPlacement(value.placement) &&
    optionalBoolean(value.confirmed) &&
    optionalBoolean(value.forceReplaceDirty);
}

function isSwitchInput(value: unknown): value is SwitchInput {
  return isRecord(value) &&
    hasOnlyKeys(value, ['instanceId', 'editorId', 'confirmed']) &&
    typeof value.instanceId === 'string' && value.instanceId.length > 0 &&
    typeof value.editorId === 'string' && value.editorId.length > 0 &&
    optionalBoolean(value.confirmed);
}

function isResetInput(value: unknown): value is { presetId: string; confirmed?: boolean } {
  return isRecord(value) &&
    hasOnlyKeys(value, ['presetId', 'confirmed']) &&
    typeof value.presetId === 'string' && value.presetId.length > 0 &&
    optionalBoolean(value.confirmed);
}

function isEmptyInput(value: unknown): value is Record<string, never> {
  return isRecord(value) && Object.keys(value).length === 0;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isEditorPlacement(value: unknown): value is EditorPlacement {
  if (!isRecord(value) || typeof value.mode !== 'string') return false;
  if (value.mode === 'floating' || value.mode === 'popout') {
    return hasOnlyKeys(value, ['mode', 'bounds']) &&
      (value.bounds === undefined || isBounds(value.bounds));
  }
  if (value.mode === 'drawer') return hasOnlyKeys(value, ['mode', 'edge']) && isEdge(value.edge);
  if (value.mode === 'split') {
    return hasOnlyKeys(value, ['mode', 'direction', 'relativeToInstanceId']) &&
      isSplitDirection(value.direction) && optionalString(value.relativeToInstanceId);
  }
  if (value.mode === 'replace' || value.mode === 'tab') {
    return hasOnlyKeys(value, ['mode', 'relativeToInstanceId']) && optionalString(value.relativeToInstanceId);
  }
  return false;
}

function isBounds(value: unknown): boolean {
  if (!isRecord(value) || !hasOnlyKeys(value, ['left', 'top', 'width', 'height'])) return false;
  const entries = ['left', 'top', 'width', 'height'].map((key) => value[key]);
  return entries.every((entry) => typeof entry === 'number' && Number.isFinite(entry)) &&
    (value.left as number) >= 0 && (value.top as number) >= 0 &&
    (value.width as number) > 0 && (value.height as number) > 0;
}

function isEdge(value: unknown): boolean {
  return value === 'left' || value === 'right' || value === 'top' || value === 'bottom';
}

function isSplitDirection(value: unknown): boolean {
  return value === 'left' || value === 'right' || value === 'above' || value === 'below';
}

function optionalString(value: unknown): boolean {
  return value === undefined || typeof value === 'string';
}

function optionalBoolean(value: unknown): boolean {
  return value === undefined || typeof value === 'boolean';
}

function hasOnlyKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const allowed = new Set(keys);
  return Object.keys(value).every((key) => allowed.has(key));
}
