import assert from 'node:assert/strict';
import test from 'node:test';

import { commands } from '../src/commands.ts';

test('every registered command parses input and delegates through the typed gateway', async () => {
  const calls = [];
  const gateway = {
    validateRecipe: async (input) => (calls.push(['validate', input]), { valid: true, warnings: [] }),
    planPreview: async (input) => (calls.push(['preview', input]), { previewId: 'preview_1', mode: 'mock' }),
    publishRecipe: async (input) => (calls.push(['publish', input]), { published: true, mode: 'mock' }),
    setBindingEnabled: async (input) => (calls.push(['binding', input]), { changed: true, mode: 'mock' }),
  };
  const inputs = [
    { recipeId: 'vfxrec_1' },
    { recipeId: 'vfxrec_1', qualityTier: 'medium' },
    { recipeId: 'vfxrec_1', changeSetId: 'chg_1' },
    { recipeId: 'vfxrec_1', bindingId: 'vfxbind_1', enabled: true, changeSetId: 'chg_1' },
  ];
  assert.equal(commands.length, 4);
  for (const [index, command] of commands.entries()) {
    const parsed = command.inputSchema.parse(inputs[index]);
    await command.execute(parsed, gateway);
  }
  assert.deepEqual(calls.map(([name]) => name), ['validate', 'preview', 'publish', 'binding']);
});

test('runtime schemas reject malformed command inputs', () => {
  assert.throws(() => commands[0].inputSchema.parse({ recipeId: '' }), TypeError);
  assert.throws(() => commands[1].inputSchema.parse({ recipeId: 'vfxrec_1', qualityTier: 'ultra' }), TypeError);
  assert.throws(() => commands[2].inputSchema.parse({ recipeId: 'vfxrec_1' }), TypeError);
  assert.throws(() => commands[3].inputSchema.parse({ recipeId: 'vfxrec_1', bindingId: 'x', enabled: 'yes', changeSetId: 'chg_1' }), TypeError);
});
