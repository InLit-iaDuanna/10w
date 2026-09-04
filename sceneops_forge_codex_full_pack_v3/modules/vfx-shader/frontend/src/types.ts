import type { ComponentType } from 'react';

export type ExecutionMode = 'live' | 'cached' | 'mock' | 'planned' | 'blocked';
export type QualityTier = 'low' | 'medium' | 'high';
export type EditorViewState =
  | { kind: 'loading' }
  | { kind: 'empty' }
  | { kind: 'failed'; code: string; message: string; retryable: boolean }
  | { kind: 'offline'; integration: 'unity' | 'render' }
  | { kind: 'permission'; requiredPermission: string }
  | { kind: 'disabled' }
  | { kind: 'ready'; recipe: VfxRecipeView; mode: ExecutionMode };

export interface VfxParameterView {
  key: string;
  labelZh: string;
  kind: 'float' | 'integer' | 'boolean' | 'color';
  value: number | boolean | string;
  minimum?: number;
  maximum?: number;
}

export interface VfxRecipeView {
  recipeId: string;
  titleZh: string;
  qualityTier: QualityTier;
  parameters: VfxParameterView[];
  warningMessages: string[];
  bindingCount: number;
  enabledBindingCount: number;
  approvalState: 'proposed' | 'approved' | 'rejected' | 'published';
}

export interface VfxShaderEditorProps {
  state: EditorViewState;
  onRetry?: () => void;
  onCreateRecipe?: () => void;
  onParameterChange?: (key: string, value: number | boolean | string) => void;
  onRequestApproval?: () => void;
}

export interface CommandAvailability {
  available: boolean;
  code?: 'MODULE_DISABLED' | 'PERMISSION_DENIED' | 'INTEGRATION_OFFLINE';
  messageZh?: string;
}

export interface CommandDefinition<TInput, TResult> {
  id: string;
  title: string;
  requiredPermissions: string[];
  optionalIntegrations?: Array<'unity' | 'render'>;
  inputSchema: { parse(value: unknown): TInput };
  canExecute(input: TInput, context: CommandContext): CommandAvailability;
  execute(input: TInput, gateway: VfxCommandGateway): Promise<TResult>;
}

export interface CommandContext {
  moduleEnabled: boolean;
  permissions: ReadonlySet<string>;
  integrations: Readonly<Record<'unity' | 'render', boolean>>;
}

export interface VfxCommandGateway {
  validateRecipe(input: { recipeId: string }): Promise<{ valid: boolean; warnings: string[] }>;
  planPreview(input: { recipeId: string; qualityTier: QualityTier }): Promise<{ previewId: string; mode: ExecutionMode }>;
  publishRecipe(input: { recipeId: string; changeSetId: string }): Promise<{ published: boolean; mode: ExecutionMode }>;
  setBindingEnabled(input: { recipeId: string; bindingId: string; enabled: boolean; changeSetId: string }): Promise<{ changed: boolean; mode: ExecutionMode }>;
}

export interface PreviewView {
  previewId: string;
  passes: string[];
  seed: number;
  frameCount: number;
  qualityTier: QualityTier;
  warnings: string[];
  mode: ExecutionMode;
}

export type PreviewViewState =
  | { kind: 'loading' }
  | { kind: 'empty' }
  | { kind: 'failed'; code: string; message: string }
  | { kind: 'offline'; integration: 'render' }
  | { kind: 'permission'; requiredPermission: string }
  | { kind: 'disabled' }
  | { kind: 'ready'; preview: PreviewView };

export interface VfxPreviewEditorProps {
  state: PreviewViewState;
  onRetry?: () => void;
  onPlanPreview?: () => void;
}

export interface EditorDefinition<TProps> {
  id: string;
  title: string;
  icon: string;
  category: 'vfx';
  defaultPlacement: 'right' | 'center';
  minWidth: number;
  minHeight: number;
  singleton: boolean;
  requiredPermissions: string[];
  optionalIntegrations: Array<'unity' | 'render'>;
  load: () => Promise<{ default: ComponentType<TProps> }>;
}
