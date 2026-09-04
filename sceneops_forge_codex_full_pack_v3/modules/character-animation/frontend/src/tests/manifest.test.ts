import { describe, expect, it } from 'vitest';
import { moduleContribution } from '../index';

describe('character animation module contribution', () => {
  it('registers all six lazy editors and seven commands', async () => {
    expect(moduleContribution.manifest).toEqual({
      id: 'character-animation',
      version: '0.1.0',
      featureFlag: 'character_animation',
    });
    expect(moduleContribution.editors.map((editor) => editor.id)).toEqual([
      'character.editor',
      'character.rig-inspector',
      'character.skin-qa',
      'animation.timeline',
      'animation.retarget-preview',
      'animation.animator-graph',
    ]);
    expect(moduleContribution.commands.map((command) => command.id)).toHaveLength(7);
    const loaded = await Promise.all(moduleContribution.editors.map((editor) => editor.load()));
    expect(loaded.every((entry) => typeof entry.default === 'function')).toBe(true);
  });

  it('declares permission, integration, size, and state contracts for every editor', () => {
    for (const editor of moduleContribution.editors) {
      expect(editor.requiredPermissions.length).toBeGreaterThan(0);
      expect(editor.optionalIntegrations).toBeDefined();
      expect(editor.minWidth).toBeGreaterThanOrEqual(340);
      expect(editor.minHeight).toBeGreaterThanOrEqual(240);
      expect(editor.serializeState(editor.restoreState(undefined))).toBeDefined();
    }
  });
});
