import assert from 'node:assert/strict';
import test from 'node:test';

import { uiCommands } from '../src/commands/uiCommands.ts';
import { labSessionForProject } from '../src/lab-session.ts';

test('integrated lab session uses the UUID carried by the project identity', () => {
  assert.equal(
    labSessionForProject('prj_1234567890abcdef1234567890abcdef'),
    '12345678-90ab-cdef-1234-567890abcdef',
  );
  assert.throws(() => labSessionForProject('prj_not-a-uuid'), /项目身份/);
});

const inputs = [
  { flowId: 'flow.key-door' },
  { mappingId: 'map_key', changeSetId: 'cs_key' },
  { changeSetId: 'cs_key' },
  { changeSetId: 'cs_key' },
];

test('UI commands validate input and use the shared gateway', async () => {
  const calls = [];
  const context = {
    enabled: true,
    unityOnline: true,
    permissions: ['ui:read', 'ui:write', 'ui:publish'],
    gateway: { execute: async (id, input) => (calls.push([id, input]), { ok: true }) },
  };
  for (const [index, command] of uiCommands.entries()) await command.execute(context, inputs[index]);
  assert.deepEqual(calls.map(([id]) => id), uiCommands.map(({ id }) => id));
});

test('UI commands reject missing fields and unavailable execution', async () => {
  assert.throws(() => uiCommands[0].inputSchema.parse({}), /flowId/);
  assert.throws(() => uiCommands[1].inputSchema.parse({ mappingId: 'map_key' }), /changeSetId/);
  assert.throws(() => uiCommands[2].inputSchema.parse({ changeSetId: 'cs_key', approverId: 'spoofed' }), /未知字段/);
  const disabled = { enabled: false, unityOnline: false, permissions: [], gateway: { execute: async () => null } };
  await assert.rejects(uiCommands[0].execute(disabled, inputs[0]), /UI_COMMAND_UNAVAILABLE: disabled/);
});
