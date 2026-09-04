import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { manifest } from '../manifest.ts';
import { BUILT_IN_WORKSPACE_PRESETS, HOME_PRESET, JUDGE_PRESET } from '../fixtures/workspace-presets.ts';
import { moduleContribution } from '../index.ts';
import type { WorkspaceCoordinator } from '../state/workspace-coordinator.ts';

test('manifest declares dockview-react as the shell docking engine', () => {
  assert.equal(manifest.dockingEngine, 'dockview-react');
  const packageJson = JSON.parse(readFileSync(new URL('../../package.json', import.meta.url), 'utf8'));
  assert.equal(packageJson.dependencies['dockview-react'], '8.2.0');
  const dockingDependencies = Object.keys(packageJson.dependencies).filter((name) => name.includes('dock'));
  assert.deepEqual(dockingDependencies, ['dockview-react']);
  const yaml = readFileSync(new URL('../../../module.yaml', import.meta.url), 'utf8');
  assert.match(yaml, /id: forge-shell/);
  assert.match(yaml, /docking_engine: dockview-react/);
  assert.match(yaml, /entrypoints:\n  frontend: \.\/frontend\/src\/index\.ts/);
  const manifestSchema = JSON.parse(readFileSync(new URL('../../../schemas/module-manifest-v1.schema.json', import.meta.url), 'utf8'));
  const eventSchema = JSON.parse(readFileSync(new URL('../../../schemas/shell-events-v1.schema.json', import.meta.url), 'utf8'));
  const layoutSchema = JSON.parse(readFileSync(new URL('../../../schemas/workspace-layout-v3.schema.json', import.meta.url), 'utf8'));
  assert.match(manifestSchema.$id, /module-manifest-v1/);
  assert.match(eventSchema.$id, /shell-events-v1/);
  assert.match(layoutSchema.$id, /workspace-layout-v3/);
});

test('all required presets exist and Home has no dashboard regression', () => {
  assert.deepEqual(BUILT_IN_WORKSPACE_PRESETS.map((preset) => preset.id), [
    'home', 'design', 'assets', 'character', 'world', 'logic', 'render', 'build', 'playtest', 'review', 'judge',
  ]);
  assert.deepEqual(HOME_PRESET.editors, [{
    editorId: 'assistant.conversation', placement: { mode: 'tab' }, executionMode: 'live',
  }]);
  assert.ok(Object.values(HOME_PRESET.drawerModes ?? {}).every((mode) => mode === 'hidden'));
  assert.equal(HOME_PRESET.editors.some((entry) => entry.editorId.includes('dashboard')), false);
  assert.equal(JUDGE_PRESET.judgeMode, true);
  assert.ok(JUDGE_PRESET.editors.every((entry) => entry.executionMode === 'mock'));
});

test('every advertised shell command has a runtime contribution', () => {
  const runtimeCommandIds = moduleContribution
    .createCommands({} as WorkspaceCoordinator)
    .map((command) => command.id);
  assert.deepEqual(runtimeCommandIds, manifest.contributes.commands);
});
