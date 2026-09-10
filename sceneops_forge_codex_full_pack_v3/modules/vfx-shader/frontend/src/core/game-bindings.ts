import * as THREE from 'three/webgpu';
import { parseProject, type LookdevProject } from './lookdev';
import { nodeMaterial } from './render-scene';

/** Build every material first; commit only after the caller's GPU validation succeeds. */
export async function bindLookdevMaterials(
  root: THREE.Object3D,
  input: LookdevProject,
  validate: (candidate: THREE.Object3D) => Promise<void>,
): Promise<() => void> {
  const project = parseProject(input);
  const meshes = new Map<string, THREE.Mesh>();
  root.traverse(node => {
    if (!(node as THREE.Mesh).isMesh) return;
    const id = node.userData.sceneops_id;
    if (typeof id !== 'string') return;
    if (meshes.has(id)) throw new Error(`Duplicate sceneops_id: ${id}`);
    meshes.set(id, node as THREE.Mesh);
  });
  const generated: THREE.Material[] = [];
  const assignments: Array<{mesh: THREE.Mesh; before: THREE.Material | THREE.Material[]; after: THREE.Material | THREE.Material[]}> = [];
  try {
    for (const object of project.objects) {
      const mesh = meshes.get(object.id);
      if (!mesh) throw new Error(`Missing sceneops_id: ${object.id}`);
      const original = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      if (object.materialSlots.length !== original.length) throw new Error(`Material slots changed: ${object.id}`);
      const next = original.map((material, slot) => {
        const binding = object.materialSlots.find(item => item.slot === slot);
        const state = project.materials.find(item => item.id === binding?.materialId);
        if (!state) throw new Error(`Missing material slot: ${object.id}/${slot}`);
        const result = nodeMaterial(state, material, !!mesh.geometry.getAttribute('uv'), !!mesh.geometry.getAttribute('tangent'));
        generated.push(result);
        return result;
      });
      assignments.push({ mesh, before: mesh.material, after: Array.isArray(mesh.material) ? next : next[0] });
    }
    for (const item of assignments) item.mesh.material = item.after;
    await validate(root);
  } catch (error) {
    for (const item of assignments) item.mesh.material = item.before;
    generated.forEach(material => material.dispose());
    throw error;
  }
  return () => {
    for (const item of assignments) if (item.mesh.material === item.after) item.mesh.material = item.before;
    generated.forEach(material => material.dispose());
  };
}
