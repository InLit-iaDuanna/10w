import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  createDemoProject, applyOperations, isolateMaterialSlot, validateOperations, parseProject,
  getExportWarnings, createLight, DEFAULT_EFFECT,
} from '../src/core/lookdev';
import { encodeProject, decodeProject } from '../src/core/project-package';
import { nodeMaterial, buildRenderScene } from '../src/core/render-scene';
import { createDemoScene, inspectGlbContainer } from '../src/core/three-lookdev';
import * as THREE from 'three/webgpu';

void test('局部编辑共享材质时复制实例，并保持其他材质槽不变', () => {
  const before = createDemoProject();
  before.objects[1].materialSlots[0].materialId = 'mat-shell';
  before.objects[1].materialSlots.push({ slot: 1, materialId: 'mat-shell', sourceMaterialId: 'mat-shell' });
  const { project, materialId, isolated } = isolateMaterialSlot(before, 'demo-shell', 0);
  assert.equal(isolated, true);
  const after = applyOperations(project, [{ kind: 'material.update', targetId: materialId, patch: { baseColor: '#b87333' } }], 'manual', '改铜色');
  assert.equal(after.materials.find((m) => m.id === 'mat-shell')!.baseColor, '#183650');
  assert.equal(after.materials.find((m) => m.id === materialId)!.baseColor, '#b87333');
  assert.equal(after.objects[1].materialSlots[1].materialId, 'mat-shell');
  assert.equal(before.materials.length, 3);
});

void test('单独材质无需新建实例', () => {
  assert.equal(isolateMaterialSlot(createDemoProject(), 'demo-shell', 0).isolated, false);
});

void test('混合有效和无效操作的事务不修改原状态', () => {
  const p = createDemoProject();
  const original = structuredClone(p);
  assert.throws(() => applyOperations(p, [
    { kind: 'material.update', targetId: 'mat-shell', patch: { roughness: 0.4 } },
    { kind: 'material.update', targetId: 'unknown', patch: { roughness: 0.6 } },
  ], 'ai', '错误事务'));
  assert.deepEqual(p, original);
});

void test('拒绝 NaN、未知字段、几何操作与参数越界', () => {
  const p = createDemoProject();
  for (const op of [
    { kind: 'material.update', targetId: 'mat-shell', patch: { roughness: 2 } },
    { kind: 'material.update', targetId: 'mat-shell', patch: { roughness: NaN } },
    { kind: 'material.update', targetId: 'mat-shell', patch: { name: '注入' } },
    { kind: 'geometry.update', targetId: 'demo-shell' },
    { kind: 'material.update', targetId: 'mat-shell', patch: {}, script: 'bad' },
  ]) assert.throws(() => validateOperations(p, [op]));
});

void test('执行层强制材质与灯光范围', () => {
  const p = createDemoProject();
  const scope = { materialIds: ['mat-shell'], lightIds: p.lights.map((l) => l.id), lighting: false };
  assert.throws(() => validateOperations(p, [{ kind: 'material.update', targetId: 'mat-glass', patch: { opacity: 0 } }], scope));
  assert.throws(() => validateOperations(p, [{ kind: 'light.update', targetId: 'light-key', patch: { intensity: 20 } }], scope));
  assert.throws(() => validateOperations(p, [{ kind: 'environment.update', patch: { intensity: 0 } }], scope));
});

void test('灯光编辑保持对象、材质与相机不变', () => {
  const p = createDemoProject();
  const next = applyOperations(p, [
    { kind: 'light.update', targetId: 'light-key', patch: { intensity: 2 } },
    { kind: 'environment.update', patch: { rotation: 0.5 } },
  ], 'manual', '调整照明');
  assert.deepEqual(next.objects, p.objects); assert.deepEqual(next.materials, p.materials);
  assert.deepEqual(next.view, p.view); assert.equal(next.editLog.length, 1);
});

void test('同事务重复灯光 ID 被拒绝', () => {
  const light = createLight('point', 'new-light', '点光');
  assert.throws(() => applyOperations(createDemoProject(), [
    { kind: 'light.add', light }, { kind: 'light.add', light },
  ], 'ai', '添加'));
});

void test('工程包重开完整恢复参数、灯光、相机和撤销/重做快照', async () => {
  const before = createDemoProject();
  const after = applyOperations(before, [
    { kind: 'material.effect.set', targetId: 'mat-shell', effect: { ...DEFAULT_EFFECT, type: 'checker', direction: 36 } },
  ], 'manual', '棋盘格');
  after.view.position = [2, 3, 4];
  const bundle = { project: after, history: { past: [before], future: [] }, source: null };
  const bytes = await encodeProject(bundle);
  const reopened = await decodeProject(bytes.buffer as ArrayBuffer);
  assert.deepEqual(reopened, bundle);
  assert.deepEqual(parseProject(reopened.history.past[0]), before);
});

void test('工程拒绝断开的材质引用、重复 ID 和不支持的版本', () => {
  const a = createDemoProject(); a.objects[0].materialSlots[0].materialId = 'missing';
  const b = createDemoProject(); b.materials.push(b.materials[0]);
  assert.throws(() => parseProject(a)); assert.throws(() => parseProject(b));
  assert.throws(() => parseProject({ ...createDemoProject(), version: 5 }));
});

void test('导出警告只统计实际引用的程序化材质', () => {
  const p = createDemoProject();
  p.materials.push({ ...structuredClone(p.materials[0]), id: 'unused', procedural: { ...DEFAULT_EFFECT, type: 'noise' } });
  assert.equal(getExportWarnings(p).length, 2);
  p.materials[0].procedural.type = 'noise';
  assert.equal(getExportWarnings(p).length, 3);
  p.materials[0].procedural.type = 'none'; p.environment = { intensity: 0, rotation: 0 }; p.lights = [];
  assert.deepEqual(getExportWarnings(p), []);
});

void test('节点材质保留原纹理、alphaTest 与双面设置', () => {
  const source = new THREE.MeshStandardMaterial({ roughness: 0.3, side: THREE.DoubleSide, alphaTest: 0.5 });
  const texture = new THREE.Texture();
  source.map = texture; source.normalMap = texture; source.roughnessMap = texture;
  const state = createDemoProject().materials[0]; state.alphaMode = 'MASK'; state.alphaCutoff = 0.5;
  const result = nodeMaterial(state, source, true);
  assert.equal(result.map, texture); assert.equal(result.normalMap, texture);
  assert.equal(result.roughnessMap, texture); assert.equal(result.side, THREE.DoubleSide);
  assert.equal(result.alphaTest, 0.5); assert.notEqual(result, source);
});

void test('无 UV 的程序化编辑失败，源材质与几何不变', () => {
  const source = createDemoScene();
  const first = source.children[0] as THREE.Mesh;
  first.geometry.deleteAttribute('uv');
  const original = first.material;
  const project = createDemoProject(); project.materials[0].procedural.type = 'noise';
  assert.throws(() => buildRenderScene(source, project, new THREE.Texture()), /UV/);
  assert.equal(first.material, original);
  assert.equal(source.children.length, 3);
});

void test('三种程序化算法可以构建颜色和粗糙度节点', () => {
  for (const type of ['noise', 'stripes', 'checker'] as const) {
    for (const target of ['color', 'roughness'] as const) {
      const state = createDemoProject().materials[0]; state.procedural = { ...DEFAULT_EFFECT, type, target };
      const m = nodeMaterial(state, new THREE.MeshStandardMaterial(), true);
      assert.ok(target === 'color' ? m.colorNode : m.roughnessNode);
    }
  }
});

void test('GLB 输入拒绝截断文件和外部资源引用', () => {
  assert.throws(() => inspectGlbContainer(new ArrayBuffer(3)));
  const data = new TextEncoder().encode(JSON.stringify({ asset: { version: '2.0' }, images: [{ uri: 'https://example.com/a.png' }] }));
  const size = Math.ceil(data.length / 4) * 4;
  const bytes = new ArrayBuffer(20 + size); const view = new DataView(bytes);
  view.setUint32(0, 0x46546c67, true); view.setUint32(4, 2, true); view.setUint32(8, bytes.byteLength, true);
  view.setUint32(12, size, true); view.setUint32(16, 0x4e4f534a, true);
  new Uint8Array(bytes, 20).fill(32); new Uint8Array(bytes, 20, data.length).set(data);
  assert.throws(() => inspectGlbContainer(bytes), /外部资源/);
});
