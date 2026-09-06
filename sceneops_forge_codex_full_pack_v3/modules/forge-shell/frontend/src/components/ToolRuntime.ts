import { createContext, useContext, type ReactNode } from 'react';
import type { EditorDefinition, EditorPlacement, JsonValue } from '../contracts.ts';
import type { ToolLibraryCatalog } from './tool-library-tree.ts';
export interface ShellToolRuntime {
  editors: readonly EditorDefinition[];
  toolLibraryCatalog?: ToolLibraryCatalog;
  open(editorId: string, placement: EditorPlacement): Promise<void>;
  execute(commandId: string, input: JsonValue): Promise<void>;
  save(): void;
  renderTaskActivity?(projectId: string | null): ReactNode;
  renderProductionNodeStatus?(projectId: string | null, moduleId: string): ReactNode;
}
export const ShellToolRuntimeContext = createContext<ShellToolRuntime | null>(null);
export function useShellTools(): ShellToolRuntime {
  const value = useContext(ShellToolRuntimeContext);
  if (!value) throw new Error('工具运行时尚未连接');
  return value;
}
