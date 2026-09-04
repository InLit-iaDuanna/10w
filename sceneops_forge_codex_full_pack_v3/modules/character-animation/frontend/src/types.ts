import type { ComponentType, ReactNode } from 'react';
import type { ZodType } from 'zod';
import type { paths } from './generated/api';

export type ExecutionMode = 'live' | 'cached' | 'mock' | 'planned' | 'blocked';
export type EditorPlacement = 'center' | 'left' | 'right' | 'bottom';
export type ContextBinding =
  | { mode: 'follow-global' }
  | { mode: 'pinned'; context: Partial<WorkbenchContext> };

export interface WorkbenchContext {
  projectId: string | null;
  selectedAssetIds: string[];
  activeFeatureId: string | null;
  activeTaskId: string | null;
  activeChangeSetId: string | null;
  timelineTime?: number;
}

export interface CharacterAnimationApiPort {
  post<TRequest, TResult>(path: CharacterAnimationPostPath, request: TRequest): Promise<TResult>;
}

export type CharacterAnimationPostPath = {
  [Path in keyof paths]: paths[Path] extends { post: unknown } ? Path : never;
}[keyof paths];

export interface CommandExecutionContext {
  api: CharacterAnimationApiPort;
  workbench: WorkbenchContext;
}

export interface CommandAvailability {
  available: boolean;
  code?: 'MODULE_DISABLED' | 'PERMISSION_DENIED' | 'PROJECT_REQUIRED' | 'INTEGRATION_OFFLINE';
  reason?: string;
}

export interface WorkbenchCommandDefinition<TInput, TResult> {
  id: string;
  title: string;
  inputSchema: ZodType<TInput>;
  requiredPermissions: string[];
  requiredIntegrations?: string[];
  canExecute(context: CommandGuardContext): CommandAvailability;
  execute(context: CommandExecutionContext, input: TInput): Promise<TResult>;
}

export interface CommandGuardContext {
  workbench: WorkbenchContext;
  moduleEnabled: boolean;
  permissions: Set<string>;
  integrations: Set<string>;
}

export type EditorRuntimeState<TData> =
  | { kind: 'loading'; mode: ExecutionMode; message?: string }
  | { kind: 'empty'; mode: ExecutionMode; message: string }
  | { kind: 'failure'; mode: ExecutionMode; message: string; retry?: () => void }
  | { kind: 'offline'; mode: 'blocked'; message: string; retry?: () => void }
  | { kind: 'permission'; mode: 'blocked'; message: string }
  | { kind: 'ready'; mode: ExecutionMode; data: TData };

export interface EditorProps<TState, TData> {
  instanceId: string;
  contextBinding: ContextBinding;
  localState: TState;
  updateLocalState(patch: Partial<TState>): void;
  runtime: EditorRuntimeState<TData>;
  invokeCommand<TResult>(commandId: string, input: unknown): Promise<TResult>;
}

export interface EditorDefinition<TState = unknown, TData = unknown> {
  id: string;
  title: string;
  icon: string;
  category: 'character' | 'animation';
  load(): Promise<{ default: ComponentType<EditorProps<TState, TData>> }>;
  defaultPlacement: EditorPlacement;
  minWidth: number;
  minHeight: number;
  singleton: boolean;
  requiredPermissions: string[];
  optionalIntegrations: string[];
  serializeState(state: TState): unknown;
  restoreState(value: unknown): TState;
}

export interface ModuleManifestView {
  id: 'character-animation';
  version: string;
  featureFlag: 'character_animation';
}

export interface ModuleContribution {
  manifest: ModuleManifestView;
  editors: EditorDefinition<any, any>[];
  commands: WorkbenchCommandDefinition<any, any>[];
  navigation: Array<{ editorId: string; group: string; keywords: string[]; recommendedEdges: string[] }>;
}

export interface EditorStateFrameProps<TData> {
  title: string;
  state: EditorRuntimeState<TData>;
  children(data: TData): ReactNode;
}
