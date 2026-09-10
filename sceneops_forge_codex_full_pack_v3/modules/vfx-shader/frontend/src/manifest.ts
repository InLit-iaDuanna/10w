export const manifest = {
  schemaVersion: 1,
  id: 'vfx-shader',
  version: '0.1.0',
  featureFlag: 'vfx_shader',
  editors: ['vfx.recipe', 'shader.parameters', 'vfx.preview', 'lookdev.material'],
  commands: [
    'vfx.recipe.validate',
    'vfx.preview.plan',
    'vfx.recipe.publish',
    'vfx.binding.set_enabled',
  ],
  optionalIntegrations: ['unity', 'render'],
} as const;
