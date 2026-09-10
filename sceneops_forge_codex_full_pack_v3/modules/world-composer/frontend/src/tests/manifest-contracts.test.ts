import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import test from 'node:test';

import * as publicApi from '../index.ts';
import { evaluateWorldCommandAvailability, worldCommandDefinitions } from '../commands.ts';
import { moduleContribution } from '../manifest.ts';
import { moduleRootUrl, readJson } from './test-helpers.ts';

interface DiskManifest {
  schema_version: number;
  id: string;
  feature_flag: string;
  requires: { modules: string[]; integrations: string[]; optional_integrations: string[] };
  contributes: {
    editors: string[];
    commands: string[];
    events: string[];
    jobs: string[];
    workflows: string[];
    policy_gates: string[];
  };
  entrypoints: { frontend: string };
}

test('module manifest is valid YAML-compatible JSON and matches actual contributions', () => {
  const manifest = readJson<DiskManifest>('module.yaml');
  assert.equal(manifest.schema_version, 1);
  assert.equal(manifest.id, 'world-composer');
  assert.equal(manifest.feature_flag, 'world_composer');
  assert.deepEqual(manifest.contributes.editors, moduleContribution.editors.map((editor) => editor.id));
  assert.deepEqual(manifest.contributes.commands, moduleContribution.commands.map((command) => command.id));
  assert.deepEqual(manifest.contributes.events, moduleContribution.events);
  assert.deepEqual(manifest.contributes.jobs, moduleContribution.jobs.map((job) => job.id));
  assert.deepEqual(manifest.contributes.workflows, moduleContribution.workflows.map((workflow) => workflow.id));
  assert.deepEqual(manifest.contributes.policy_gates, moduleContribution.policyGates.map((gate) => gate.id));
  assert.ok(manifest.requires.modules.includes('core-kernel'));
  assert.ok(manifest.requires.modules.includes('module-runtime'));
  assert.ok(manifest.requires.modules.includes('asset-library'));
  assert.equal(manifest.entrypoints.frontend, './frontend/src/index.ts');
});

test('public entrypoint exposes the registered module and canonical domain operations', () => {
  assert.equal(publicApi.moduleContribution.manifest.id, 'world-composer');
  for (const name of [
    'validateAnnotation',
    'createAssetPlacementPlan',
    'restoreIssueContext',
    'validateLevel',
    'compilePlacementRecipe',
    'DeterministicMockWorldMutationAdapter',
  ]) {
    assert.equal(typeof publicApi[name as keyof typeof publicApi], 'function', `${name} is not public`);
  }
});

test('all on-disk contracts are versioned JSON Schemas and event payloads do not duplicate envelopes', () => {
  const schemaPaths = [
    'contracts/manifests/world-annotation-document.schema.json',
    'contracts/manifests/world-level-document.schema.json',
    'contracts/manifests/world-placement-recipe.schema.json',
    'contracts/events/scene.annotation.created.v1.schema.json',
    'contracts/events/scene.object.placement_proposed.v1.schema.json',
    'contracts/events/scene.level.validated.v1.schema.json',
  ];
  for (const path of schemaPaths) {
    const schema = readJson<Record<string, unknown>>(path);
    assert.equal(schema.$schema, 'https://json-schema.org/draft/2020-12/schema');
    assert.match(String(schema.$id), /\.v1\.schema\.json$/);
  }
  const eventSchema = readJson<{ description: string; properties: Record<string, unknown> }>(schemaPaths[3]!);
  assert.match(eventSchema.description, /Payload only/);
  assert.equal('event_id' in eventSchema.properties, false);
});

function collectTypeScriptFiles(directoryUrl: URL): URL[] {
  const files: URL[] = [];
  for (const name of readdirSync(directoryUrl)) {
    const child = new URL(name, directoryUrl.href.endsWith('/') ? directoryUrl : new URL(`${directoryUrl.href}/`));
    const stats = statSync(child);
    if (stats.isDirectory()) files.push(...collectTypeScriptFiles(new URL(`${child.href}/`)));
    else if (/\.tsx?$/.test(name) && !child.pathname.includes('/tests/')) files.push(child);
  }
  return files;
}

test('module product source has no shell internals, host tool SDKs, direct fetch, or unrestricted execution', () => {
  const sourceUrl = new URL('frontend/src/', moduleRootUrl);
  const source = collectTypeScriptFiles(sourceUrl)
    .map((url) => readFileSync(url, 'utf8'))
    .join('\n');
  assert.doesNotMatch(source, /dockview|UnityEngine|bpy\.|child_process/);
  assert.doesNotMatch(source, /\bfetch\s*\(/);
  const contracts = readFileSync(new URL('frontend/src/contracts.ts', moduleRootUrl), 'utf8');
  assert.doesNotMatch(contracts, /from ['"](?:react|three)(?:['"/])/);
  assert.doesNotMatch(source, /modules\/[a-z-]+\/(?!world-composer)/);
});

test('commands expose module-disabled, permission, integration, and available states', () => {
  const capture = worldCommandDefinitions.find((command) => command.id === 'scene.capture.fixed.request');
  assert.ok(capture);
  assert.equal(
    evaluateWorldCommandAvailability(capture, {
      moduleEnabled: false,
      permissions: new Set(['scene:read']),
      connectedIntegrations: new Set(['artifact-store']),
    }).state,
    'module-disabled',
  );
  assert.equal(
    evaluateWorldCommandAvailability(capture, {
      moduleEnabled: true,
      permissions: new Set(),
      connectedIntegrations: new Set(['artifact-store']),
    }).state,
    'permission-denied',
  );
  assert.equal(
    evaluateWorldCommandAvailability(capture, {
      moduleEnabled: true,
      permissions: new Set(['scene:read']),
      connectedIntegrations: new Set(),
    }).state,
    'disconnected',
  );
  assert.equal(
    evaluateWorldCommandAvailability(capture, {
      moduleEnabled: true,
      permissions: new Set(['scene:read']),
      connectedIntegrations: new Set(['artifact-store']),
    }).available,
    true,
  );
});
