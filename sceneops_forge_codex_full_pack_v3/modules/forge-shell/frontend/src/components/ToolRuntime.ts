import { createContext, useContext } from 'react';
import type { EditorDefinition, EditorPlacement, JsonValue } from '../contracts.ts';
export interface ShellToolRuntime {
  editors: readonly EditorDefinition[];
  open(editorId: string, placement: EditorPlacement): Promise<void>;
  execute(commandId: string, input: JsonValue): Promise<void>;
  save(): void;
}
export const ShellToolRuntimeContext = createContext<ShellToolRuntime | null>(null);
export function useShellTools(): ShellToolRuntime {
  const value = useContext(ShellToolRuntimeContext);
  if (!value) throw new Error('工具运行时尚未连接');
  return value;
}
