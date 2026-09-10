import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import * as THREE from 'three/webgpu';
import ts from 'typescript';
import { expandShaderGraphOperations, proposalPrompt } from '../src/core/ai-proposal';
import {
  applyOperations, createDemoProject, DEFAULT_EFFECT, editResponseSchema, parseProject, validateOperations, type LookdevOperation,
} from '../src/core/lookdev';
import {
  createHologramGraph, encodeShaderGraphWire, graphParameters, parseShaderGraph, parseShaderGraphWire,
  patchShaderGraphParameters, shaderGraphUsesTime, type ShaderGraph,
} from '../src/core/shader-graph';
import { nodeMaterial } from '../src/core/render-scene';
import { decodeProject, encodeProject } from '../src/core/project-package';
import { encodeShaderPackage, generateTslMaterialModule } from '../src/core/shader-package';
import JSZip from 'jszip';

function combinedSurfaceGraph(): ShaderGraph {
  return parseShaderGraph({
    version: 1,
    name: '条纹与颗粒组合',
    description: '彩色条纹写入颜色，独立噪声写入粗糙度。',
    nodes: [
      { id: 'uv', kind: 'input.uv' },
      { id: 'stripeScale', kind: 'parameter.float', key: 'stripeScale', label: '条纹密度', value: 12, min: 1, max: 80 },
      { id: 'stripeUv', kind: 'math.multiply', a: 'uv', b: 'stripeScale' },
      { id: 'stripes', kind: 'pattern.stripes', coordinate: 'stripeUv' },
      { id: 'stripeStrength', kind: 'parameter.float', key: 'stripeStrength', label: '条纹强度', value: 0.65, min: 0, max: 1 },
      { id: 'stripeMask', kind: 'math.multiply', a: 'stripes', b: 'stripeStrength' },
      { id: 'baseColor', kind: 'input.materialColor' },
      { id: 'accent', kind: 'parameter.color', key: 'accentColor', label: '条纹颜色', value: '#E05AFF' },
      { id: 'surfaceColor', kind: 'math.mix', a: 'baseColor', b: 'accent', factor: 'stripeMask' },
      { id: 'noiseScale', kind: 'parameter.float', key: 'noiseScale', label: '颗粒密度', value: 24, min: 1, max: 100 },
      { id: 'noiseUv', kind: 'math.multiply', a: 'uv', b: 'noiseScale' },
      { id: 'noise', kind: 'pattern.noise', coordinate: 'noiseUv' },
      { id: 'half', kind: 'value.float', value: 0.5 },
      { id: 'noiseCentered', kind: 'math.subtract', a: 'noise', b: 'half' },
      { id: 'roughStrength', kind: 'parameter.float', key: 'roughStrength', label: '颗粒强度', value: 0.25, min: 0, max: 1 },
      { id: 'roughDelta', kind: 'math.multiply', a: 'noiseCentered', b: 'roughStrength' },
      { id: 'baseRoughness', kind: 'input.materialRoughness' },
      { id: 'roughCombined', kind: 'math.add', a: 'baseRoughness', b: 'roughDelta' },
      { id: 'zero', kind: 'value.float', value: 0 },
      { id: 'one', kind: 'value.float', value: 1 },
      { id: 'roughness', kind: 'math.clamp', input: 'roughCombined', min: 'zero', max: 'one' },
    ],
    outputs: { color: 'surfaceColor', roughness: 'roughness' },
  });
}

void test('一张材质图同时组合颜色条纹和粗糙度噪声', () => {
  const project = createDemoProject();
  const graph = combinedSurfaceGraph();
  const next = applyOperations(project, [{ kind: 'material.graph.set', targetId: 'mat-shell', graph }], 'ai', '组合双层表面');
  assert.equal(next.materials[0].shaderGraph?.outputs.color, 'surfaceColor');
  assert.equal(next.materials[0].shaderGraph?.outputs.roughness, 'roughness');
  const material = nodeMaterial(next.materials[0], new THREE.MeshStandardMaterial(), true);
  assert.ok(material.colorNode);
  assert.ok(material.roughnessNode);
});

void test('全息图连接时间、轮廓、发光和透明输出并可构建 TSL', () => {
  const graph = createHologramGraph();
  assert.equal(shaderGraphUsesTime(graph), true);
  assert.deepEqual(Object.keys(graph.outputs), ['color', 'roughness', 'emissive', 'opacity']);
  const state = createDemoProject().materials[0];
  state.shaderGraph = graph;
  const material = nodeMaterial(state, new THREE.MeshStandardMaterial(), false);
  assert.ok(material.colorNode);
  assert.ok(material.roughnessNode);
  assert.ok(material.emissiveNode);
  assert.ok(material.opacityNode);
  assert.equal(material.transparent, true);
  assert.equal(material.depthWrite, false);
});

void test('后续修改只更新命名参数，不改变图拓扑和其他值', () => {
  const graph = createHologramGraph();
  const beforeTopology = graph.nodes.map(({ id, kind }) => ({ id, kind }));
  const before = Object.fromEntries(graphParameters(graph).map((node) => [node.key, node.value]));
  const patched = patchShaderGraphParameters(graph, { scanSpeed: 0.4, rimColor: '#9B5CFF' });
  const after = Object.fromEntries(graphParameters(patched).map((node) => [node.key, node.value]));
  assert.deepEqual(patched.nodes.map(({ id, kind }) => ({ id, kind })), beforeTopology);
  assert.equal(after.scanSpeed, 0.4);
  assert.equal(after.rimColor, '#9B5CFF');
  assert.equal(after.scanColor, before.scanColor);
  assert.equal(after.scanDensity, before.scanDensity);
  assert.equal(graphParameters(graph).find((node) => node.key === 'scanSpeed')?.value, 0.8);
});

void test('图参数修改经过操作合同、范围和单次事务历史', () => {
  let project = createDemoProject();
  project = applyOperations(project, [{ kind: 'material.graph.set', targetId: 'mat-shell', graph: createHologramGraph() }], 'ai', '生成全息图');
  const operation: LookdevOperation = { kind: 'material.graph.patch', targetId: 'mat-shell', parameters: { scanSpeed: 0.4, rimColor: '#9B5CFF' } };
  const next = applyOperations(project, [operation], 'ai', '速度减半并调整轮廓色');
  assert.equal(next.revision, 2);
  assert.equal(next.editLog.length, 2);
  assert.throws(() => validateOperations(project, [{ ...operation, targetId: 'mat-glass' }], { materialIds: ['mat-shell'], lightIds: [], lighting: false }));
  assert.throws(() => validateOperations(project, [{ kind: 'material.graph.patch', targetId: 'mat-shell', parameters: { missing: 1 } }]));
});

void test('材质图拒绝循环、断开节点、错误类型、任意源码和超预算', () => {
  const graph = createHologramGraph();
  const cycle = structuredClone(graph);
  const height = cycle.nodes.find((node) => node.id === 'height') as Extract<typeof cycle.nodes[number], { kind: 'vector.component' }>;
  height.input = 'movingHeight';
  assert.throws(() => parseShaderGraph(cycle), /循环/);

  const disconnected = structuredClone(graph);
  disconnected.nodes.push({ id: 'unused', kind: 'value.float', value: 0.5 });
  assert.throws(() => parseShaderGraph(disconnected), /没有连接/);

  const wrongOutput = structuredClone(graph);
  wrongOutput.outputs.opacity = 'surfaceColor';
  assert.throws(() => parseShaderGraph(wrongOutput), /opacity 输出/);

  assert.throws(() => parseShaderGraph({ ...graph, source: 'return arbitraryWGSL();' }));
  assert.throws(() => parseShaderGraph({ ...graph, nodes: Array.from({ length: 65 }, (_, index) => ({ id: `node${index}`, kind: 'value.float', value: 0 })) }));
});

void test('旧固定效果不再允许在同一事务中静默相互覆盖', () => {
  const project = createDemoProject();
  assert.throws(() => applyOperations(project, [
    { kind: 'material.effect.set', targetId: 'mat-shell', effect: { ...DEFAULT_EFFECT, type: 'stripes', target: 'color' } },
    { kind: 'material.effect.set', targetId: 'mat-shell', effect: { ...DEFAULT_EFFECT, type: 'noise', target: 'roughness' } },
  ], 'ai', '两个固定效果'), /使用材质图/);
});

void test('工程包保存材质图、参数和撤销快照，旧 v5 状态可读取', async () => {
  const before = createDemoProject();
  const project = applyOperations(before, [{ kind: 'material.graph.set', targetId: 'mat-shell', graph: createHologramGraph() }], 'ai', '生成全息图');
  const bytes = await encodeProject({ project, history: { past: [before], future: [] }, source: null });
  const reopened = await decodeProject(bytes.buffer as ArrayBuffer);
  assert.deepEqual(reopened.project.materials[0].shaderGraph, project.materials[0].shaderGraph);
  assert.equal(reopened.history.past[0].materials[0].shaderGraph, null);

  const legacy = structuredClone(before) as unknown as { materials: Array<Record<string, unknown>> };
  for (const material of legacy.materials) delete material.shaderGraph;
  assert.equal(parseProject(legacy).materials[0].shaderGraph, null);
});

void test('Shader 交付包包含图、基础材质、确定性 TSL 模块和版本说明', async () => {
  const material = createDemoProject().materials[0];
  material.shaderGraph = createHologramGraph();
  const source = generateTslMaterialModule(material);
  assert.match(source, /material\.emissiveNode/);
  assert.match(source, /material\.opacityNode/);
  assert.match(source, /parameters\.scanSpeed/);
  assert.doesNotMatch(source, /eval\(|new Function/);
  const bytes = await encodeShaderPackage(material);
  const zip = await JSZip.loadAsync(bytes);
  assert.deepEqual(Object.keys(zip.files).sort(), ['README.md', 'lumaform-material.ts', 'material-graph.json', 'material-state.json', 'package.json']);
  assert.deepEqual(JSON.parse(await zip.file('material-graph.json')!.async('string')), material.shaderGraph);
  assert.match(await zip.file('README.md')!.async('string'), /Three\.js 0\.185\.1/);
});

void test('Shader 交付包中的 TSL 模块通过独立 TypeScript 编译', async () => {
  const material = createDemoProject().materials[0];
  material.shaderGraph = createHologramGraph();
  const directory = await mkdtemp(path.join(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'), '.lumaform-shader-test-'));
  const file = path.join(directory, 'lumaform-material.ts');
  try {
    await writeFile(file, generateTslMaterialModule(material));
    const program = ts.createProgram([file], {
      module: ts.ModuleKind.ESNext,
      moduleResolution: ts.ModuleResolutionKind.Bundler,
      target: ts.ScriptTarget.ES2022,
      noEmit: true,
      skipLibCheck: true,
      strict: true,
    });
    const diagnostics = ts.getPreEmitDiagnostics(program);
    assert.equal(diagnostics.length, 0, diagnostics.map((diagnostic) => ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n')).join('\n'));
  } finally {
    await rm(directory, { recursive: true });
  }
});

void test('AI 紧凑节点 IR 无损展开为完整材质图', () => {
  const graph = createHologramGraph();
  const wire = encodeShaderGraphWire(graph);
  assert.deepEqual(parseShaderGraphWire(wire), graph);
  assert.ok(JSON.stringify(wire).length < JSON.stringify(graph).length * 0.7);
  assert.throws(() => parseShaderGraphWire({ ...wire, nodes: [['bad', 'source.javascript', 'alert(1)']] }), /不支持的紧凑 Shader 节点类型/);
});

void test('AI proposal expands graphs, preserves status and refuses executable operations', () => {
  const graph = createHologramGraph();
  const result = editResponseSchema.parse(expandShaderGraphOperations({ status: 'applied', summary: '创建材质图', operations: [{ kind: 'material.graph.set', targetId: 'mat-shell', graph: encodeShaderGraphWire(graph) }] }));
  assert.deepEqual(result.operations[0], { kind: 'material.graph.set', targetId: 'mat-shell', graph });
  assert.match(proposalPrompt(createDemoProject(), { materialIds: ['mat-shell'], lightIds: [], lighting: false }), /material\.graph\.set/);
  assert.throws(() => editResponseSchema.parse({ status: 'applied', summary: '危险源码', operations: [{ kind: 'material.shader.source', targetId: 'mat-shell', source: 'arbitrary code' }] }));
});
