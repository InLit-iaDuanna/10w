import type { EditorDefinition, VfxPreviewEditorProps, VfxShaderEditorProps } from './types';
import { commands } from './commands';
import { manifest } from './manifest';

const recipeEditor: EditorDefinition<VfxShaderEditorProps> = {
    id: 'vfx.recipe', title: 'VFX Recipe', icon: 'sparkles', category: 'vfx',
    defaultPlacement: 'right', minWidth: 360, minHeight: 260, singleton: false,
    requiredPermissions: ['vfx:read'], optionalIntegrations: ['unity', 'render'],
    load: () => import('./editors/VfxRecipeEditor'),
};
const parameterEditor: EditorDefinition<VfxShaderEditorProps> = {
    id: 'shader.parameters', title: 'Shader 参数', icon: 'sliders', category: 'vfx',
    defaultPlacement: 'right', minWidth: 320, minHeight: 240, singleton: false,
    requiredPermissions: ['vfx:write'], optionalIntegrations: ['unity', 'render'],
    load: () => import('./editors/VfxShaderEditor'),
};
const previewEditor: EditorDefinition<VfxPreviewEditorProps> = {
    id: 'vfx.preview', title: 'VFX 预览', icon: 'eye', category: 'vfx',
    defaultPlacement: 'center', minWidth: 420, minHeight: 280, singleton: false,
    requiredPermissions: ['vfx:read'], optionalIntegrations: ['render'],
    load: () => import('./editors/VfxPreviewEditor'),
};

export const editors = [recipeEditor, parameterEditor, previewEditor] as const;

export const moduleContribution = {
  manifest,
  editors,
  commands,
  navigation: [
    { editorId: 'vfx.recipe', group: '内容制作', keywords: ['VFX', '特效', 'Shader'], recommendedEdges: ['right'] },
    { editorId: 'vfx.preview', group: '内容制作', keywords: ['预览', 'overdraw'], recommendedEdges: ['right'] },
  ],
} as const;

export { commands, manifest };
export type * from './types';
