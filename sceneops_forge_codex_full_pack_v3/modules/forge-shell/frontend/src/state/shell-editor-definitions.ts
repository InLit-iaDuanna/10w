import type { EditorDefinition, JsonValue } from '../contracts.ts';

interface ToolLibraryState extends Record<string, JsonValue> {
  query: string;
  selectedGroup: string | null;
}

interface CommandSearchState extends Record<string, JsonValue> {
  query: string;
  selectedCommandId: string | null;
}

export const toolLibraryEditor: EditorDefinition<ToolLibraryState> = {
  id: 'shell.tool-library',
  title: '工具库',
  icon: 'library',
  category: 'system',
  load: () => import('../components/ToolLibraryEditor.tsx'),
  defaultPlacement: { mode: 'drawer', edge: 'left' },
  minWidth: 240,
  minHeight: 220,
  singleton: true,
  initialState: () => ({ query: '', selectedGroup: null }),
  serializeState: (state) => structuredClone(state),
  restoreState: restoreToolLibraryState,
};

export const commandSearchEditor: EditorDefinition<CommandSearchState> = {
  id: 'shell.command-search',
  title: '命令搜索',
  icon: 'search',
  category: 'system',
  load: () => import('../components/CommandSearchEditor.tsx'),
  defaultPlacement: { mode: 'drawer', edge: 'top' },
  minWidth: 320,
  minHeight: 120,
  singleton: true,
  initialState: () => ({ query: '', selectedCommandId: null }),
  serializeState: (state) => structuredClone(state),
  restoreState: restoreCommandSearchState,
};

export const SHELL_EDITOR_DEFINITIONS: EditorDefinition[] = [toolLibraryEditor, commandSearchEditor];

function restoreToolLibraryState(value: JsonValue): ToolLibraryState {
  return isRecord(value) && typeof value.query === 'string'
    ? { query: value.query, selectedGroup: stringOrNull(value.selectedGroup) }
    : { query: '', selectedGroup: null };
}

function restoreCommandSearchState(value: JsonValue): CommandSearchState {
  return isRecord(value) && typeof value.query === 'string'
    ? { query: value.query, selectedCommandId: stringOrNull(value.selectedCommandId) }
    : { query: '', selectedCommandId: null };
}

function stringOrNull(value: JsonValue | undefined): string | null {
  return typeof value === 'string' ? value : null;
}

function isRecord(value: JsonValue): value is { [key: string]: JsonValue } {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}
