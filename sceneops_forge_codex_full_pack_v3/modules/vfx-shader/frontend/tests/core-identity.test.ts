import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three/webgpu';
import { inspectImportedScene } from '../src/core/three-lookdev';
import { assertAssetBindings, buildRenderScene } from '../src/core/render-scene';

test('sceneops_id survives rename and hierarchy order, extras remain unchanged', () => {
  const scene = new THREE.Group();
  const material = new THREE.MeshStandardMaterial();
  material.userData.lookdevSourceMaterialId = 'material-fixture';
  for (const id of ['object-a', 'object-b']) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(), material);
    mesh.userData = { sceneops_id: id, custom_asset_tag: 'retained' };
    scene.add(mesh);
  }
  const project = inspectImportedScene(scene, 'asset.glb');
  scene.children.reverse();
  scene.children[0].name = 'renamed';
  assertAssetBindings(scene, project);
  assert.deepEqual(project.objects.map(object => object.id), ['object-a', 'object-b']);
  assert.equal(scene.children[0].userData.custom_asset_tag, 'retained');
  scene.children[0].userData.sceneops_id = 'object-a';
  assert.throws(() => inspectImportedScene(scene, 'asset.glb'), /重复/);
});

test('Imported light bindings follow stable identity across hierarchy reorder', () => {
  const root = new THREE.Group();
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(), new THREE.MeshStandardMaterial());
  mesh.userData.sceneops_id = 'mesh';
  (mesh.material as THREE.Material).userData.lookdevSourceMaterialId = 'material-fixture';
  root.add(mesh);
  for (const id of ['light-a', 'light-b']) {
    const light = new THREE.PointLight();
    light.userData.sceneops_id = id;
    root.add(light);
  }
  const project = inspectImportedScene(root, 'lights.glb');
  project.lights[0].intensity = 17;
  project.lights[1].intensity = 31;
  root.children.reverse();
  const rendered = buildRenderScene(root, project, new THREE.Texture());
  try {
    for (const state of project.lights) {
      const carrier = rendered.content.children.find(node => node.userData.sceneops_id === state.id)!;
      assert.equal((carrier.children[0] as THREE.Light).intensity, state.intensity);
    }
  } finally { rendered.dispose(); }
});
