import { characterAnimationCommands } from './commands';
import { characterAnimationEditors } from './editorDefinitions';
import type { ModuleContribution, ModuleManifestView } from './types';

export const manifest: ModuleManifestView = {
  id: 'character-animation',
  version: '0.1.0',
  featureFlag: 'character_animation',
};

export const moduleContribution: ModuleContribution = {
  manifest,
  editors: characterAnimationEditors,
  commands: characterAnimationCommands,
  navigation: characterAnimationEditors.map((editor) => ({
    editorId: editor.id,
    group: editor.category === 'character' ? '角色' : '动画',
    keywords: [editor.title, editor.id, 'rig', 'skin', 'animation'],
    recommendedEdges: editor.defaultPlacement === 'center' ? ['right'] : [editor.defaultPlacement],
  })),
};
