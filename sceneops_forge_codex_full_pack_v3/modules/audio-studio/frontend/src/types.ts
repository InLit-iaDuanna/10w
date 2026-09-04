import type { ReactElement } from 'react';

export type ExecutionMode = 'live' | 'cached' | 'mock' | 'planned' | 'blocked';
export type AudioInspectionView = { waveformPeaks: number[]; format: string; channels: number; sampleRateHz: number; bitDepth: number; durationSeconds: number; peakDbfs: number; approximateLoudnessDbfs: number; warnings: string[] };
export type AudioMappingView = { gameplayEvent: string; audioAssetId: string; targetSceneopsId: string; audioSourceName: string; mixerGroup: string };
export type AudioEditorState = { selectedAssetId?: string; selectedEvent?: string; mode: ExecutionMode; viewState: 'loading' | 'empty' | 'ready' | 'failed' | 'offline' | 'disabled' | 'permission-denied'; errorMessage?: string; analysis?: AudioInspectionView; mapping?: AudioMappingView };
export type CommandAvailability = { available: boolean; reason?: string };
export type AudioCommandInput = Record<string, unknown>;
export type RuntimeInputSchema = { parse: (input: unknown) => AudioCommandInput };
export type AudioCommandGateway = { execute: (commandId: string, input: AudioCommandInput) => Promise<unknown> };
export type AudioCommand = {
  id: string;
  title: string;
  requiredPermissions: string[];
  inputSchema: RuntimeInputSchema;
  canExecute: (input: { moduleEnabled: boolean; unityOnline: boolean }) => CommandAvailability;
  execute: (gateway: AudioCommandGateway, input: unknown, availability: { moduleEnabled: boolean; unityOnline: boolean }) => Promise<unknown>;
};
export type AudioEditor = {
  id: 'audio.studio'; title: string; icon: 'waveform'; category: 'content'; defaultPlacement: 'bottom';
  minWidth: number; minHeight: number; requiredPermissions: ['audio:read'];
  optionalIntegrations: ['unity', 'artifact-store', 'media-generation']; singleton: true;
  load: () => Promise<{ default: (props: { state: AudioEditorState; onRetry?: () => void }) => ReactElement }>;
};
export type ModuleContribution = { manifest: { id: 'audio-studio'; featureFlag: 'audio_studio' }; editors: AudioEditor[]; commands: AudioCommand[] };
