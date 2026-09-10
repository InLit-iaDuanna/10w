import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDemoProject, isolateMaterialSlot } from '../src/core/lookdev';
import { createDemoScene, inspectImportedScene, loadGlbScene } from '../src/core/three-lookdev';
import { assertAssetBindings, exportGlb, disposeAsset } from '../src/core/render-scene';

class BlobReader {
  result: ArrayBuffer | string | null = null;
  onloadend: (() => void) | null = null;
  readAsArrayBuffer(blob: Blob) { void blob.arrayBuffer().then(bytes => { this.result = bytes; this.onloadend?.(); }); }
  readAsDataURL(blob: Blob) { void blob.arrayBuffer().then(bytes => { this.result = 'data:' + blob.type + ';base64,' + Buffer.from(bytes).toString('base64'); this.onloadend?.(); }); }
}
function rewrite(bytes: ArrayBuffer, change: (json: any) => void): ArrayBuffer {
  const original = new DataView(bytes);
  const oldLength = original.getUint32(12, true);
  const json = JSON.parse(new TextDecoder().decode(new Uint8Array(bytes, 20, oldLength)));
  change(json);
  const encoded = new TextEncoder().encode(JSON.stringify(json));
  const length = Math.ceil(encoded.length / 4) * 4;
  const tail = new Uint8Array(bytes, 20 + oldLength);
  const result = new ArrayBuffer(20 + length + tail.length);
  const view = new DataView(result);
  view.setUint32(0, 0x46546c67, true); view.setUint32(4, 2, true); view.setUint32(8, result.byteLength, true);
  view.setUint32(12, length, true); view.setUint32(16, 0x4e4f534a, true);
  const content = new Uint8Array(result);
  content.fill(0x20, 20, 20 + length); content.set(encoded, 20); content.set(tail, 20 + length);
  return result;
}

test('Real GLB appended/reordered material arrays retain source bindings and independent current identities', async () => {
  const previous = globalThis.FileReader;
  globalThis.FileReader = BlobReader as unknown as typeof FileReader;
  const scenes: Awaited<ReturnType<typeof loadGlbScene>>[] = [];
  try {
    const fixture = createDemoScene();
    scenes.push(fixture);
    const bytes = await exportGlb(fixture, createDemoProject());
    const shared = rewrite(bytes, json => { for (const mesh of json.meshes) mesh.primitives[0].material = 0; });
    const source = await loadGlbScene(shared); scenes.push(source);
    const project = inspectImportedScene(source, 'shared.glb');
    assert.equal(project.materials.length, 1);
    const isolated = isolateMaterialSlot(project, project.objects[0].id, 0);
    const applied = rewrite(shared, json => {
      const duplicate = Object.fromEntries(Object.entries(structuredClone(json.materials[0])).reverse());
      const edited = structuredClone(json.materials[0]);
      edited.extras.lookdevMaterialId = isolated.materialId;
      edited.pbrMetallicRoughness.roughnessFactor = 0.22;
      const duplicateIndex = json.materials.push(duplicate) - 1;
      const editedIndex = json.materials.push(edited) - 1;
      json.meshes[0].primitives[0].material = editedIndex;
      json.meshes[2].primitives[0].material = duplicateIndex;
      const count = json.materials.length;
      json.materials.reverse();
      for (const mesh of json.meshes) for (const primitive of mesh.primitives) primitive.material = count - 1 - primitive.material;
    });
    const reopened = await loadGlbScene(applied); scenes.push(reopened);
    assertAssetBindings(reopened, isolated.project);
    const inspected = inspectImportedScene(reopened, 'applied.glb');
    assert.equal(inspected.materials.length, 2, 'Equivalent appended clones share one current material identity');
    assert.equal(inspected.materials.find(material => material.id === isolated.materialId)?.roughness, 0.22);
    assert.ok(inspected.objects.every(object => object.materialSlots[0].sourceMaterialId === project.objects[0].materialSlots[0].sourceMaterialId));
    const conflicting = rewrite(applied, json => {
      const duplicate = json.materials[json.meshes[2].primitives[0].material];
      duplicate.pbrMetallicRoughness.roughnessFactor = 0.91;
    });
    const conflictScene = await loadGlbScene(conflicting); scenes.push(conflictScene);
    assert.throws(() => inspectImportedScene(conflictScene, 'conflict.glb'), /冲突内容/);
    await assert.rejects(loadGlbScene(rewrite(shared, json => { delete json.materials[0].extras.lookdevSourceMaterialId; })), /缺少持久/);
  } finally {
    scenes.forEach(disposeAsset);
    globalThis.FileReader = previous;
  }
});
