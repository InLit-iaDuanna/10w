import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const src = join(dirname(fileURLToPath(import.meta.url)), '..');

describe('frontend ownership boundaries', () => {
  it('keeps editors free of direct external calls and docking internals', () => {
    const files = [
      'CharacterEditor.tsx',
      'RigInspectorEditor.tsx',
      'SkinQaEditor.tsx',
      'AnimationTimelineEditor.tsx',
      'RetargetPreviewEditor.tsx',
      'AnimatorGraphEditor.tsx',
    ];
    for (const file of files) {
      const source = readFileSync(join(src, 'editors', file), 'utf8');
      expect(source).not.toContain('fetch(');
      expect(source).not.toContain('dockview');
      expect(source).not.toContain('UnityEngine');
      expect(source).not.toContain('bpy');
    }
  });
});
