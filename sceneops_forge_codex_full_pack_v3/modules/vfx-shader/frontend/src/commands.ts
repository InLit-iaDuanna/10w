import type {
  CommandAvailability,
  CommandContext,
  CommandDefinition,
  QualityTier,
} from './types';

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new TypeError('input must be an object');
  return value as Record<string, unknown>;
}

function text(value: unknown, key: string): string {
  if (typeof value !== 'string' || value.length === 0) throw new TypeError(`${key} must be a non-empty string`);
  return value;
}

const validateInputSchema = { parse(value: unknown) { const input = record(value); return { recipeId: text(input.recipeId, 'recipeId') }; } };
const previewInputSchema = { parse(value: unknown) { const input = record(value); const qualityTier = input.qualityTier; if (!['low', 'medium', 'high'].includes(String(qualityTier))) throw new TypeError('qualityTier is invalid'); return { recipeId: text(input.recipeId, 'recipeId'), qualityTier: qualityTier as QualityTier }; } };
const publishInputSchema = { parse(value: unknown) { const input = record(value); return { recipeId: text(input.recipeId, 'recipeId'), changeSetId: text(input.changeSetId, 'changeSetId') }; } };
const bindingInputSchema = { parse(value: unknown) { const input = record(value); if (typeof input.enabled !== 'boolean') throw new TypeError('enabled must be boolean'); return { recipeId: text(input.recipeId, 'recipeId'), bindingId: text(input.bindingId, 'bindingId'), enabled: input.enabled, changeSetId: text(input.changeSetId, 'changeSetId') }; } };

function authoringAvailability(context: CommandContext, permission: string): CommandAvailability {
  if (!context.moduleEnabled) return { available: false, code: 'MODULE_DISABLED', messageZh: 'VFX/Shader 模块已停用' };
  if (!context.permissions.has(permission)) return { available: false, code: 'PERMISSION_DENIED', messageZh: `缺少 ${permission} 权限` };
  return { available: true };
}

function unityAvailability(context: CommandContext, permission: string): CommandAvailability {
  const base = authoringAvailability(context, permission);
  if (!base.available) return base;
  if (!context.integrations.unity) return { available: false, code: 'INTEGRATION_OFFLINE', messageZh: 'Unity 未连接；可继续编辑和预览' };
  return base;
}

export const validateRecipeCommand: CommandDefinition<
  { recipeId: string },
  { valid: boolean; warnings: string[] }
> = {
  id: 'vfx.recipe.validate',
  title: '校验 VFX Recipe',
  requiredPermissions: ['vfx:read'],
  inputSchema: validateInputSchema,
  canExecute: (_input, context) => authoringAvailability(context, 'vfx:read'),
  execute: (input, gateway) => gateway.validateRecipe(input),
};

export const planPreviewCommand: CommandDefinition<
  { recipeId: string; qualityTier: QualityTier },
  { previewId: string; mode: import('./types').ExecutionMode }
> = {
  id: 'vfx.preview.plan',
  title: '规划确定性预览',
  requiredPermissions: ['vfx:read'],
  optionalIntegrations: ['render'],
  inputSchema: previewInputSchema,
  canExecute: (_input, context) => authoringAvailability(context, 'vfx:read'),
  execute: (input, gateway) => gateway.planPreview(input),
};

export const publishRecipeCommand: CommandDefinition<
  { recipeId: string; changeSetId: string },
  { published: boolean; mode: import('./types').ExecutionMode }
> = {
  id: 'vfx.recipe.publish',
  title: '发布已审批 VFX Recipe',
  requiredPermissions: ['vfx:publish'],
  optionalIntegrations: ['unity'],
  inputSchema: publishInputSchema,
  canExecute: (_input, context) => unityAvailability(context, 'vfx:publish'),
  execute: (input, gateway) => gateway.publishRecipe(input),
};

export const setBindingEnabledCommand: CommandDefinition<
  { recipeId: string; bindingId: string; enabled: boolean; changeSetId: string },
  { changed: boolean; mode: import('./types').ExecutionMode }
> = {
  id: 'vfx.binding.set_enabled',
  title: '启用或停用 VFX 绑定',
  requiredPermissions: ['vfx:write'],
  optionalIntegrations: ['unity'],
  inputSchema: bindingInputSchema,
  canExecute: (_input, context) => unityAvailability(context, 'vfx:write'),
  execute: (input, gateway) => gateway.setBindingEnabled(input),
};

export const commands = [
  validateRecipeCommand,
  planPreviewCommand,
  publishRecipeCommand,
  setBindingEnabledCommand,
] as const;
