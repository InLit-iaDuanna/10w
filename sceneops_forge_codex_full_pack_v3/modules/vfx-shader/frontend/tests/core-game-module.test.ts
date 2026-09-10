import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';
import ts from 'typescript';
import { spawnSync } from 'node:child_process';
import { generateGameModule } from '../src/core/game-module';
import { createDemoProject } from '../src/core/lookdev';
import { createHologramGraph } from '../src/core/shader-graph';

test('Portable mixed graph and procedural runtime compiles deterministically', async () => {
  const project = createDemoProject();
  project.materials[0].shaderGraph = createHologramGraph();
  project.materials[1].procedural.type = 'stripes';
  project.lights[0].intensity=6;
  project.lights[0].sourceLightIndex=0;
  project.editLog.push({id:'light-edit',at:'2026-09-10T00:00:00Z',source:'manual',summary:'Edit imported light',operations:[{kind:'light.update',targetId:project.lights[0].id,patch:{intensity:6}}]});
  const code = generateGameModule(project);
  assert.equal(code, generateGameModule(project));
  const directory = await mkdtemp(path.join(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), '.lookdev-game-test-'));
  try {
    const file = path.join(directory, 'runtime.ts');
    await writeFile(file, code);
    const program = ts.createProgram([file], { module: ts.ModuleKind.ESNext, moduleResolution: ts.ModuleResolutionKind.Bundler, target: ts.ScriptTarget.ES2022, noEmit: true, skipLibCheck: true, strict: true });
    const diagnostics = ts.getPreEmitDiagnostics(program);
    assert.equal(diagnostics.length, 0, diagnostics.map(d => ts.flattenDiagnosticMessageText(d.messageText, '\n')).join('\n'));
    const runner = path.join(directory, 'runner.ts');
    await writeFile(runner, `import assert from 'node:assert/strict';
import { applySceneopsLookdev, createMaterial0 } from './runtime.ts';
import { time } from 'three/tsl';
import { createDemoScene } from '../src/core/three-lookdev.ts';
import type { Mesh } from 'three/webgpu';
import {RectAreaLight} from 'three/webgpu';
const animated = createMaterial0();
let timeConnected = false;
animated.emissiveNode!.traverse(node => { if (node === time) timeConnected = true; });
assert.equal(timeConnected, true, 'Generated graph must reference the live TSL time uniform');
time.update({ time: 1 } as any); assert.equal(time.value, 1);
time.update({ time: 2 } as any); assert.equal(time.value, 2);
animated.dispose();
const scene = createDemoScene();
const sourceLight=new RectAreaLight('#ffffff',3);sourceLight.userData.sceneops_id='light-key';scene.add(sourceLight);
const mesh = scene.children[0] as Mesh;
const original = mesh.material;
await assert.rejects(applySceneopsLookdev(scene, async () => { throw new Error('GPU validation rejected'); }), /GPU validation rejected/);
assert.equal(mesh.material, original);
assert.equal(sourceLight.intensity,3);
const restore = await applySceneopsLookdev(scene, async () => {});
assert.notEqual(mesh.material, original);
assert.equal(sourceLight.intensity,0);
assert.equal(scene.children.find(node=>node!==sourceLight&&node.userData.sceneops_id==='light-key')?.intensity,6);
restore();
assert.equal(mesh.material, original);
assert.equal(sourceLight.intensity,3);
assert.equal(scene.children.filter(node=>node.userData.sceneops_id==='light-key').length,1);
`);
    const executed = spawnSync(process.execPath, ['--import', 'tsx', runner], { cwd: path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), encoding: 'utf8' });
    assert.equal(executed.status, 0, executed.stderr);

  } finally { await rm(directory, { recursive: true }); }
});

test('Procedural-only material without a graph compiles as a real game module', async()=>{
 const project=createDemoProject();project.materials[0].procedural.type='noise';
 const directory=await mkdtemp(path.join(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),'.lookdev-procedural-test-'));
 try{
  const file=path.join(directory,'runtime.ts');await writeFile(file,generateGameModule(project));
  const program=ts.createProgram([file],{module:ts.ModuleKind.ESNext,moduleResolution:ts.ModuleResolutionKind.Bundler,target:ts.ScriptTarget.ES2022,noEmit:true,skipLibCheck:true,strict:true});
  const diagnostics=ts.getPreEmitDiagnostics(program);
  assert.equal(diagnostics.length,0,diagnostics.map(d=>ts.flattenDiagnosticMessageText(d.messageText,'\n')).join('\n'));
 }finally{await rm(directory,{recursive:true});}
});
