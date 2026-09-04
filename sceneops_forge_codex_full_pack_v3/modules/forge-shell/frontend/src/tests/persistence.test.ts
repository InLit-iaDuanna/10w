import test from 'node:test';
import assert from 'node:assert/strict';
import { EditorRegistry } from '../state/editor-registry.ts';
import { createWorkspaceFromPreset } from '../state/workspace-factory.ts';
import {
  DebouncedLayoutWriter,
  LayoutRepository,
  exportLayout,
  importLayout,
} from '../state/layout-persistence.ts';
import { HOME_PRESET } from '../fixtures/workspace-presets.ts';
import { createPresetMockEditors, deterministicIdentifierFactory } from '../fixtures/mock-shell-fixtures.ts';

class MemoryStorage {
  readonly values = new Map<string, string>();
  getItem(key: string) { return this.values.get(key) ?? null; }
  setItem(key: string, value: string) { this.values.set(key, value); }
  removeItem(key: string) { this.values.delete(key); }
}

function home() {
  const editors = new EditorRegistry();
  editors.registerAll(createPresetMockEditors());
  return createWorkspaceFromPreset(HOME_PRESET, editors, deterministicIdentifierFactory());
}

test('save, restore, export, import, and reset preserve a valid layout', () => {
  const storage = new MemoryStorage();
  const repository = new LayoutRepository(storage);
  const document = home();
  repository.save('layout', document);
  const restored = repository.load('layout', home);
  assert.equal(restored.status, 'restored');
  assert.deepEqual(restored.document, document);

  const exported = exportLayout(document);
  assert.ok(exported.endsWith('\n'));
  assert.deepEqual(importLayout(exported), document);
  assert.equal(repository.reset('layout', home).workspaceId, 'home');
  assert.equal(repository.load('layout', home).status, 'missing');
});

test('version 1 and 2 migrations are deterministic', () => {
  const storage = new MemoryStorage();
  const repository = new LayoutRepository(storage);
  storage.setItem('v1', JSON.stringify({
    schemaVersion: 1,
    workspace_id: 'home',
    areas: [{ editor_id: 'assistant.conversation', placement: 'center', locked: false }],
    drawers: { left: 'hidden', right: 'hidden', top: 'hidden', bottom: 'hidden' },
  }));
  const first = repository.load('v1', home);
  const second = repository.load('v1', home);
  assert.equal(first.status, 'migrated');
  assert.deepEqual(first, second);
  assert.equal(first.document.schemaVersion, 3);
  assert.equal(Object.values(first.document.instances)[0]?.executionMode, 'planned');
  const migratedLayout = first.document.dockviewLayout;
  assert.equal(
    typeof migratedLayout === 'object' && migratedLayout !== null && !Array.isArray(migratedLayout)
      ? migratedLayout.kind
      : null,
    'preset',
  );

  const version2 = structuredClone(home()) as unknown as Record<string, unknown>;
  version2.schemaVersion = 2;
  delete version2.floatingGroups;
  delete version2.popoutGroups;
  delete version2.maximizedAreaId;
  storage.setItem('v2', JSON.stringify(version2));
  const migrated = repository.load('v2', home);
  assert.equal(migrated.status, 'migrated');
  assert.deepEqual(migrated.document.floatingGroups, []);
  assert.deepEqual(migrated.document.popoutGroups, []);
});

test('corrupt, unsupported, and structurally invalid data recover to Home', () => {
  const storage = new MemoryStorage();
  const repository = new LayoutRepository(storage);
  storage.setItem('corrupt', '{');
  const corrupt = repository.load('corrupt', home);
  assert.equal(corrupt.status, 'recovered');
  if (corrupt.status === 'recovered') assert.equal(corrupt.reason, 'CORRUPT_JSON');

  storage.setItem('future', JSON.stringify({ schemaVersion: 99 }));
  const future = repository.load('future', home);
  assert.equal(future.status, 'recovered');
  if (future.status === 'recovered') assert.equal(future.reason, 'UNSUPPORTED_SCHEMA');

  const invalid = home();
  invalid.areas[0]!.tabs.push('missing');
  storage.setItem('invalid', JSON.stringify(invalid));
  const recovered = repository.load('invalid', home);
  assert.equal(recovered.status, 'recovered');
  assert.equal(recovered.reason, 'INVALID_LAYOUT');
  assert.equal(recovered.document.workspaceId, 'home');
});

test('debounced writer persists only the latest document and can flush synchronously', () => {
  const storage = new MemoryStorage();
  const repository = new LayoutRepository(storage);
  const writer = new DebouncedLayoutWriter(repository, 10_000);
  const first = home();
  const second = home();
  second.title = '最新布局';
  writer.schedule('layout', first);
  writer.schedule('layout', second);
  writer.flush();
  assert.equal(repository.load('layout', home).document.title, '最新布局');
  writer.cancel();
});

test('a customized workspace derived from Home remains persistable', () => {
  const storage = new MemoryStorage();
  const repository = new LayoutRepository(storage);
  const document = home();
  const conversation = document.areas[0]!.activeInstanceId!;
  document.customized = true;
  document.instances.tool = {
    ...document.instances[conversation]!,
    instanceId: 'tool',
    editorId: 'shell.tool-library',
    title: '工具库',
    executionMode: 'mock',
  };
  document.areas[0]!.tabs.push('tool');
  document.areas[0]!.activeInstanceId = 'tool';
  repository.save('custom-home', document);
  assert.equal(repository.load('custom-home', home).status, 'restored');
});

test('validation rejects malformed active tabs, execution modes, and bounds', () => {
  const storage = new MemoryStorage();
  const repository = new LayoutRepository(storage);
  const invalid = home() as unknown as Record<string, unknown>;
  const areas = invalid.areas as Array<Record<string, unknown>>;
  areas[0]!.activeInstanceId = 'missing';
  storage.setItem('bad-active', JSON.stringify(invalid));
  assert.equal(repository.load('bad-active', home).status, 'recovered');

  const badMode = home() as unknown as Record<string, unknown>;
  const instances = badMode.instances as Record<string, Record<string, unknown>>;
  Object.values(instances)[0]!.executionMode = 'pretend-live';
  storage.setItem('bad-mode', JSON.stringify(badMode));
  assert.equal(repository.load('bad-mode', home).status, 'recovered');
});

test('registered-editor hydration rejects disabled editors and restores local state', () => {
  const storage = new MemoryStorage();
  const editors = new EditorRegistry();
  editors.registerAll(createPresetMockEditors());
  const repository = new LayoutRepository(storage, editors);
  const document = home();
  const instance = Object.values(document.instances)[0]!;
  instance.editorId = 'disabled.editor';
  storage.setItem('disabled', JSON.stringify(document));
  assert.equal(repository.load('disabled', home).status, 'recovered');
});
