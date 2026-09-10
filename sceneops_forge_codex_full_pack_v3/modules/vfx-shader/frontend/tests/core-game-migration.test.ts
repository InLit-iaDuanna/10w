import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import ts from 'typescript';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { migrateLookdevGame } from '../../scripts/migrate-lookdev-game';

test('Typed migration supports async function and method, rejects sync constructor before writes', async () => {
  const directory = await mkdtemp(path.join(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), '.lookdev-migration-test-'));
  const file = path.join(directory, 'main.ts');
  try {
    await writeFile(path.join(directory, 'package.json'), JSON.stringify({ type: 'module', dependencies: { three: '0.185.1' } }));
    await writeFile(file, `import * as THREE from 'three';\nconst renderer = new THREE.WebGLRenderer();\nconst scene = new THREE.Scene(); const camera = new THREE.PerspectiveCamera();\nasync function frame() { renderer.render(scene, camera); }\nclass Game { async update() { renderer.render(scene, camera); } }\nvoid frame(); void new Game().update();`);
    const plan = await migrateLookdevGame(directory);
    assert.equal(plan.supported, true, plan.requirements.join('\n'));
    assert.equal(plan.applied, false);
    assert.match(await readFile(file, 'utf8'), /WebGLRenderer/);
    const result = await migrateLookdevGame(directory, true);
    assert.equal(result.applied, true);
    assert.match(await readFile(file, 'utf8'), /await renderer.renderAsync/);
    const repeated = await migrateLookdevGame(directory, true);
    assert.equal(repeated.supported, true, repeated.requirements.join('\n'));
    assert.deepEqual(repeated.changedFiles, []);
    const unsupported = `import { WebGLRenderer, Scene, PerspectiveCamera } from 'three';\nclass Game { renderer = new WebGLRenderer(); constructor() { this.renderer.render(new Scene(), new PerspectiveCamera()); } }`;
    await writeFile(file, unsupported);
    const rejected = await migrateLookdevGame(directory, true);
    assert.equal(rejected.supported, false);
    assert.equal(await readFile(file, 'utf8'), unsupported);
  } finally { await rm(directory, { recursive: true }); }
});

test('Default class and functional RAF loops promote void chains and schedule only after rendering', async () => {
  const directory = await mkdtemp(path.join(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), '.lookdev-frame-test-'));
  const file = path.join(directory, 'main.ts');
  try {
    await writeFile(path.join(directory, 'package.json'), JSON.stringify({ type: 'module' }));
    await writeFile(file, `import * as THREE from 'three';
export class Game {
  private renderer = new THREE.WebGLRenderer();
  private scene = new THREE.Scene(); private camera = new THREE.PerspectiveCamera();
  start() { requestAnimationFrame(time => this.update(time)); }
  private update(time: number): void { this.draw(); requestAnimationFrame(next => this.update(next)); }
  private draw(): void { this.renderer.render(this.scene, this.camera); }
}`);
    const result = await migrateLookdevGame(directory, true);
    assert.equal(result.supported, true, result.requirements.join('\n'));
    const generated = await readFile(file, 'utf8');
    assert.match(generated, /private async update\(time: number\): Promise<void>/);
    assert.match(generated, /await this.draw\(\)/);
    assert.match(generated, /requestAnimationFrame\(async \(next\) => await this.update\(next\)\)/);
    await writeFile(file, `import type { WebGLRenderer } from 'three';
let renderer: WebGLRenderer;
function frame(): void { requestAnimationFrame(frame); renderer.render(null!, null!); }
export function start(value: WebGLRenderer) { renderer = value; requestAnimationFrame(frame); }
`);
    const functional = await migrateLookdevGame(directory, true);
    assert.equal(functional.supported, true, functional.requirements.join('\n'));
    const frame = await readFile(file, 'utf8');
    assert.ok(frame.indexOf('await renderer.renderAsync') < frame.indexOf('requestAnimationFrame(sceneopsNextFrame)'));
    const runner = path.join(directory, 'runner.ts');
    await writeFile(runner, `import assert from 'node:assert/strict';
import { start } from './main.ts';
const callbacks: Array<(time: number) => unknown> = [];
(globalThis as any).requestAnimationFrame = (callback: (time: number) => unknown) => { callbacks.push(callback); return callbacks.length; };
let release!: () => void;
let draws = 0;
const renderer = { renderAsync() { draws++; return new Promise<void>(resolve => { release = resolve; }); } };
start(renderer as any);
assert.equal(callbacks.length, 1);
const first = callbacks.shift()!(0);
assert.equal(draws, 1);
assert.equal(callbacks.length, 0, 'No next RAF can be scheduled while rendering is pending');
release(); await first;
assert.equal(callbacks.length, 1);
const second = callbacks.shift()!(16);
assert.equal(draws, 2);
assert.equal(callbacks.length, 0);
release(); await second;
assert.equal(callbacks.length, 1);
`);
    const executed = spawnSync(process.execPath, ['--import', 'tsx', runner], { cwd: path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), encoding: 'utf8' });
    assert.equal(executed.status, 0, executed.stderr);
    const program = ts.createProgram([file], { module: ts.ModuleKind.ESNext, moduleResolution: ts.ModuleResolutionKind.Bundler, target: ts.ScriptTarget.ES2022, noEmit: true, skipLibCheck: true, strict: true });
    const diagnostics = ts.getPreEmitDiagnostics(program);
    assert.equal(diagnostics.length, 0, diagnostics.map(diagnostic => ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n')).join('\n'));
  } finally { await rm(directory, { recursive: true }); }
});

test('Unknown callback, setAnimationLoop and synchronous value callers remain unchanged', async () => {
  const directory = await mkdtemp(path.join(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), '.lookdev-frame-reject-test-'));
  const file = path.join(directory, 'main.ts');
  try {
    await writeFile(path.join(directory, 'package.json'), JSON.stringify({ type: 'module' }));
    for (const body of [
      'function frame() { renderer.render(scene,camera); } renderer.setAnimationLoop(frame);',
      'function frame() { renderer.render(scene,camera); return 1; } const value = frame();',
      'function frame() { renderer.render(scene,camera); } setTimeout(frame, 10);',
      'const draw = renderer.render.bind(renderer); requestAnimationFrame(() => draw(scene, camera));',
      "requestAnimationFrame(() => renderer['render'](scene, camera));",
    ]) {
      const source = `import {WebGLRenderer,Scene,PerspectiveCamera} from 'three'; const renderer = new WebGLRenderer(); const scene = new Scene(); const camera = new PerspectiveCamera(); ${body}`;
      await writeFile(file, source);
      const result = await migrateLookdevGame(directory, true);
      assert.equal(result.supported, false, source);
      assert.equal(await readFile(file, 'utf8'), source);
    }
  } finally { await rm(directory, { recursive: true }); }
});

test('Existing WebGPU project receives compiler-compatible dependencies without rewriting source', async () => {
  const directory=await mkdtemp(path.join(path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..'),'.lookdev-gpu-version-'));
  try {
    const source="import {WebGPURenderer} from 'three/webgpu'; export const renderer=new WebGPURenderer();";
    await writeFile(path.join(directory,'main.ts'),source);
    await writeFile(path.join(directory,'package.json'),JSON.stringify({type:'module',dependencies:{three:'0.183.2'}}));
    const result=await migrateLookdevGame(directory,true);
    assert.equal(result.supported,true,result.requirements.join('\n'));
    assert.deepEqual(result.changedFiles,['package.json']);
    assert.equal(JSON.parse(await readFile(path.join(directory,'package.json'),'utf8')).dependencies.three,'0.185.1');
    assert.equal(await readFile(path.join(directory,'main.ts'),'utf8'),source);
  } finally {await rm(directory,{recursive:true});}
});
