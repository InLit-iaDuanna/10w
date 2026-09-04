import assert from 'node:assert/strict';
import test from 'node:test';

import { audioCommands } from '../src/commands.ts';

const inputs = [
  { specId: 'spec_key', projectId: 'prj_home', purpose: '钥匙拾取', intendedEvents: ['gameplay.key.picked_up'], mixerGroup: 'SFX/Interact' },
  { assetId: 'aud_key', filename: 'key.wav', uploadId: 'upload_key' },
  { gameplayEvent: 'gameplay.key.picked_up', audioAssetId: 'aud_key' },
  { mappingId: 'map_key', changeSetId: 'cs_audio', audioAssetId: 'aud_key', targetSceneopsId: 'so_key_home_01', audioSourceName: 'KeyPickupSource', mixerGroup: 'SFX/Interact' },
  { mappingId: 'map_key', changeSetId: 'cs_audio', audioAssetId: 'aud_key', targetSceneopsId: 'so_key_home_01', audioSourceName: 'KeyPickupSource', mixerGroup: 'SFX/Interact' },
];

test('audio commands validate inputs and delegate through one gateway', async () => {
  const calls = [];
  const gateway = { execute: async (id, input) => (calls.push([id, input]), { ok: true }) };
  for (const [index, command] of audioCommands.entries()) {
    await command.execute(gateway, inputs[index], { moduleEnabled: true, unityOnline: true });
  }
  assert.deepEqual(calls.map(([id]) => id), audioCommands.map(({ id }) => id));
});

test('audio commands reject missing fields and offline Unity mapping', async () => {
  assert.throws(() => audioCommands[0].inputSchema.parse({ specId: 'spec_key' }), /projectId/);
  assert.throws(() => audioCommands[2].inputSchema.parse({ gameplayEvent: 'gameplay.key.picked_up' }), /audioAssetId/);
  assert.throws(() => audioCommands[2].inputSchema.parse({ gameplayEvent: 'gameplay.key.picked_up', audioAssetId: 'aud_key', actorId: 'spoofed' }), /未知字段/);
  const gateway = { execute: async () => null };
  await assert.rejects(
    audioCommands[3].execute(gateway, inputs[3], { moduleEnabled: true, unityOnline: false }),
    /AUDIO_COMMAND_UNAVAILABLE/,
  );
});
