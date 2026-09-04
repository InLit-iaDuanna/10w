import { audioCommands } from './commands';
import type { AudioEditor, ModuleContribution } from './types';

export const audioStudioEditor: AudioEditor = {
  id: 'audio.studio', title: '音频工作室', icon: 'waveform', category: 'content', defaultPlacement: 'bottom',
  minWidth: 420, minHeight: 280, requiredPermissions: ['audio:read'],
  optionalIntegrations: ['unity', 'artifact-store', 'media-generation'], singleton: true,
  load: () => import('./editors/AudioStudioEditor'),
};

export const moduleContribution: ModuleContribution = {
  manifest: { id: 'audio-studio', featureFlag: 'audio_studio' }, editors: [audioStudioEditor], commands: audioCommands,
};

export { audioCommands } from './commands';
export { audioCommandSchemas } from './commands';
export type { AudioCommand, AudioEditorState, ExecutionMode, ModuleContribution } from './types';
export { AudioLabPanel } from './editors/AudioLabPanel';
export type { paths as AudioLabPaths, components as AudioLabComponents } from './lab-api';
