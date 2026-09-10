import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { createDemoProject, applyOperations } from '../src/core/lookdev';
import { createDemoScene, inspectGlbContainer, importedAssetMetadata } from '../src/core/three-lookdev';
import { exportGlb } from '../src/core/render-scene';
import { encodeProject, decodeProject } from '../src/core/project-package';
import * as validator from 'gltf-validator';

// GLTFExporter uses the browser FileReader API. These Node tests provide its
// Blob-reading operations; the exporter, materials and buffers are unmodified.
class BlobReader {
  result: ArrayBuffer | string | null = null;
  onloadend: (() => void) | null = null;
  readAsArrayBuffer(blob: Blob) {
    void blob.arrayBuffer().then((bytes) => { this.result = bytes; this.onloadend?.(); });
  }
  readAsDataURL(blob: Blob) {
    void blob.arrayBuffer().then((bytes) => {
      this.result = 'data:' + blob.type + ';base64,' + Buffer.from(bytes).toString('base64');
      this.onloadend?.();
    });
  }
}

void test('真实 GLTFExporter 输出通过 Khronos 校验并保留 PBR、几何与赋值', async () => {
  const previous = globalThis.FileReader;
  globalThis.FileReader = BlobReader as unknown as typeof FileReader;
  try {
    const source = createDemoScene();
    importedAssetMetadata.set(source, { extras: { asset_id: 'asset-fixture' }, copyright: 'Fixture author' });
    const p = createDemoProject();
    const next = applyOperations(p, [
      { kind: 'material.update', targetId: 'mat-shell', patch: { baseColor: '#b87333', metalness: 0.95, roughness: 0.3 } },
    ], 'manual', '铜色金属');
    const bytes = await exportGlb(source, next);
    const report = await validator.validateBytes(new Uint8Array(bytes));
    assert.equal(report.issues.numErrors, 0, JSON.stringify(report.issues.messages));
    const json = inspectGlbContainer(bytes);
    assert.equal(json.meshes.length, 3);
    assert.deepEqual((json.asset as {extras: unknown}).extras, { asset_id: 'asset-fixture' });
    assert.deepEqual((json.nodes as Array<{extras?: {sceneops_id?: string}}>).flatMap(node => node.extras?.sceneops_id ? [node.extras.sceneops_id] : []).sort(), ['demo-glass', 'demo-rubber', 'demo-shell']);
    assert.equal(json.materials[0].pbrMetallicRoughness.metallicFactor, 0.95);
    assert.equal(json.materials[0].pbrMetallicRoughness.roughnessFactor, 0.3);
    assert.ok(json.materials.some((m: { extensions?: Record<string, unknown> }) => m.extensions?.KHR_materials_transmission));
    assert.equal(source.children.length, 3);
    await mkdir('/tmp/sceneops-lookdev-export', { recursive: true });
    await writeFile('/tmp/sceneops-lookdev-export/copper-demo.glb', new Uint8Array(bytes));
    const bundle = { project: next, history: { past: [p], future: [] }, source: null };
    const zip = await encodeProject(bundle);
    await writeFile('/tmp/sceneops-lookdev-export/copper-demo.luma.zip', zip);
    assert.deepEqual(await decodeProject(zip.buffer as ArrayBuffer), bundle);
    await writeFile('/tmp/sceneops-lookdev-export/gltf-validation.json', JSON.stringify(report, null, 2));
  } finally { globalThis.FileReader = previous; }
});
