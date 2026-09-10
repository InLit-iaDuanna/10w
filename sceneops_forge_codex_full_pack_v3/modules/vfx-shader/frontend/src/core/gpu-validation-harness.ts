/** Browser-only real GPU validation harness; serve through Vite and open its HTML. */
import * as THREE from 'three/webgpu';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { createDemoProject, applyOperations } from './lookdev';
import { createDemoScene } from './three-lookdev';
import { buildRenderScene } from './render-scene';
import { validateRenderCandidate } from './render-transaction';
import { createHologramGraph } from './shader-graph';

const output = document.querySelector('pre')!;
async function run() {
  const renderer = new THREE.WebGPURenderer({ antialias: true });
  renderer.setSize(640, 480);
  document.body.append(renderer.domElement);
  await renderer.init();
  const device = (renderer.backend as THREE.WebGPUBackend & { device: GPUDevice }).device;
  if (!device) throw new Error('WebGPU device is required; no fallback validation.');
  const project = applyOperations(createDemoProject(), [{ kind: 'material.graph.set', targetId: 'mat-shell', graph: createHologramGraph() }], 'manual', 'GPU harness');
  const environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment());
  const candidate = buildRenderScene(createDemoScene(), project, environment.texture);
  const camera = new THREE.PerspectiveCamera(40, 640 / 480, 0.01, 100);
  camera.position.fromArray(project.view.position);
  camera.lookAt(new THREE.Vector3(...project.view.target));
  const target = new THREE.RenderTarget(640, 480);
  device.pushErrorScope('validation');
  await validateRenderCandidate({
    compileAndDraw: async () => { await renderer.compileAsync(candidate.scene, camera); renderer.setRenderTarget(target); renderer.render(candidate.scene, camera); },
    resetRenderTarget: () => renderer.setRenderTarget(null),
    popValidationError: () => device.popErrorScope(),
    disposeTarget: () => target.dispose(),
  });
  renderer.render(candidate.scene, camera);
  output.textContent = 'PASS: live WebGPU compile, offscreen draw, validation scope and visible draw completed.';
  document.body.dataset.status = 'passed';
}
run().catch(error => { output.textContent = String(error); document.body.dataset.status = 'failed'; });
