import type { EditorHostProps, EditorDefinition, JsonValue } from '@sceneops/core-ui';
export type LookdevEditorState = {
  entityDefinitionId?: string; assetId?: string; assetTitle?: string; assetVersion?: number; assetUrl?: string;
  sceneVersion?: number; sceneInstanceId?: string; sceneopsId?: string; materialSlot?: number;
}
export interface LookdevConversationSession {
  projectId: string; label: string; lighting: boolean;
  history(signal?: AbortSignal): Promise<import('./lookdev-client').LookdevTurn[]>;
  submit(text: string, signal?: AbortSignal, turnId?:string): Promise<{ summary: string; status: 'applied' | 'declined' | 'noop'; turnId:string; createdAt:string }>;
  setLighting(value: boolean): void;
}
export type LookdevMaterialEditorProps = EditorHostProps<LookdevEditorState> & {
  onImportModel?(file: File): Promise<void>;
  onOpenAssetLibrary?(): void;
  onDirtyChange?(dirty: boolean): void;
  onConversationTargetChange?(session: LookdevConversationSession | null): void;
  onOpenConversation?(): void;
  onApplied?(result: import('./generated/lookdev-api').components['schemas']['LookdevApplication']): void;
};
export const lookdevEditorDefinition: EditorDefinition<LookdevEditorState> = {
  id: 'lookdev.material', title: '材质与灯光', icon: 'sparkles', category: 'vfx',
  defaultPlacement: { mode: 'split', direction: 'right' }, minWidth: 320, minHeight: 380,
  singleton: false, heavy: true, renderPolicy: 'suspend-when-hidden',
  requiredPermissions: ['vfx:read'], initialState: () => ({}),
  serializeState: state => Object.fromEntries(Object.entries(state).filter(([,value])=>value!==undefined)) as JsonValue,
  restoreState: value => value && typeof value === 'object' && !Array.isArray(value) ? value as LookdevEditorState : {},
  load: () => import('./editors/LookdevMaterialEditor'),
};
