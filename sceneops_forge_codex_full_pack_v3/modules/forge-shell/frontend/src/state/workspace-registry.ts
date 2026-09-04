import type { WorkspacePreset } from '../contracts.ts';

export class WorkspaceRegistry {
  readonly #presets = new Map<string, WorkspacePreset>();

  register(preset: WorkspacePreset): void {
    if (this.#presets.has(preset.id)) throw new Error(`Workspace already registered: ${preset.id}`);
    if (preset.id === 'home') validateHome(preset);
    this.#presets.set(preset.id, preset);
  }

  registerAll(presets: readonly WorkspacePreset[]): void {
    for (const preset of presets) this.register(preset);
  }

  get(presetId: string): WorkspacePreset {
    const preset = this.#presets.get(presetId);
    if (!preset) throw new Error(`Unknown workspace: ${presetId}`);
    return preset;
  }

  list(): WorkspacePreset[] {
    return [...this.#presets.values()];
  }
}
function validateHome(preset: WorkspacePreset): void {
  const isConversationOnly =
    preset.editors.length === 1 &&
    preset.editors[0]?.editorId === 'assistant.conversation' &&
    preset.editors[0]?.placement.mode === 'tab';
  const drawersHidden = (['left', 'right', 'top', 'bottom'] as const).every(
    (edge) => (preset.drawerModes?.[edge] ?? 'hidden') === 'hidden',
  );
  if (!isConversationOnly || !drawersHidden) {
    throw new Error('Home workspace must contain only assistant.conversation with all drawers hidden');
  }
}
