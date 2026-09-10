import { parseProject, type LookdevProject } from './lookdev';
import { generateTslMaterialModule } from './shader-package';

/** Emit portable imports and fixed compiler output, never model-authored executable code. */
export function generateGameModule(input: LookdevProject): string {
  const project = parseProject(input);
  const editedLightIds=new Set(project.editLog.flatMap(entry=>entry.operations.flatMap(op=>op.kind==='light.add'?[op.light.id]:op.kind==='light.update'?[op.targetId]:[])));
  const lighting=project.lights.filter(light=>editedLightIds.has(light.id)).map(light=>{
    const constructor={directional:'DirectionalLight',point:'PointLight',spot:'SpotLight',rectArea:'RectAreaLight'}[light.type];
    const args:unknown[]=[light.color,light.intensity];
    if(light.type==='point')args.push(light.distance);
    if(light.type==='spot')args.push(light.distance,light.angle,light.penumbra);
    if(light.type==='rectArea')args.push(light.width,light.height);
    return `{const original=sourceLights.get(${JSON.stringify(light.id)});
      ${light.sourceLightIndex!==undefined?`if(!original)throw new Error('Missing source light: '+${JSON.stringify(light.id)});`:''}
      const light=new ${constructor}(${args.map(value=>JSON.stringify(value)).join(',')});
      light.name=${JSON.stringify(light.name)};light.userData.sceneops_id=${JSON.stringify(light.id)};
      light.position.set(${light.position.join(',')});light.rotation.set(${light.rotation.join(',')});light.visible=${light.enabled};
      ${light.type==='directional'||light.type==='spot'?"light.target.position.set(0,0,-1);light.add(light.target);":''}
      if(original){const intensity=original.intensity;original.intensity=0;restoreLights.push(()=>{original.intensity=intensity;});}
      root.add(light);restoreLights.push(()=>{root.remove(light);light.dispose();});}`;
  }).join('\n');
  const imports = new Set<string>();
  const factories = project.materials.map((material, index) => {
    const graph = material.shaderGraph ?? { version: 1 as const, name: 'Base material', description: 'Preserved source material color', nodes: [{ id: 'base', kind: 'input.materialColor' as const }], outputs: { color: 'base' } };
    let code = generateTslMaterialModule({ ...material, shaderGraph: graph });
    code = code.replace(/^import .*;$/gm, line => { imports.add(line); return ''; });
    return code.replaceAll('LumaformShaderParameters', `Parameters${index}`).replaceAll('defaultParameters', `defaults${index}`).replaceAll('createLumaformMaterial', `createMaterial${index}`);
  });
  return `${[...imports].join('\n')}
import type { Object3D, Mesh, Material } from 'three/webgpu';
import {DirectionalLight,PointLight,SpotLight,RectAreaLight,Light} from 'three/webgpu';
${factories.join('\n')}
const project = ${JSON.stringify(project)};
const requiresUv = ${JSON.stringify(project.materials.map(material => !!material.shaderGraph?.nodes.some(node => node.kind === 'input.uv')))};
const factories = [${project.materials.map((_, i) => `createMaterial${i}`).join(',')}];
export function assignSceneopsPrimitiveIds(gltf: { parser: { associations: Map<object, { meshes?: number; primitives?: number }>; json: { meshes: { primitives: { extras?: { sceneops_id?: string } }[] }[] } } }) {
  for (const [object, reference] of gltf.parser.associations) {
    const mesh = object as Mesh;
    if (!mesh.isMesh || reference.meshes === undefined || reference.primitives === undefined) continue;
    const definition = gltf.parser.json.meshes[reference.meshes];
    if (definition.primitives.length < 2) continue;
    const primitiveId = definition.primitives[reference.primitives].extras?.sceneops_id;
    const ownerId = mesh.parent?.userData.sceneops_id;
    if (typeof primitiveId !== 'string' || typeof ownerId !== 'string') throw new Error('Missing primitive stable identity');
    mesh.userData.sceneops_id = ownerId + ':' + primitiveId;
  }
}
// Pause the game render loop while awaiting this transaction; validate must compile and draw.
export async function applySceneopsLookdev(root: Object3D, validate: (root: Object3D) => Promise<void>): Promise<() => void> {
  const meshes = new Map<string, Mesh>();
  root.traverse(node => {
    if (!(node as Mesh).isMesh) return;
    const id = node.userData.sceneops_id;
    if (typeof id !== 'string') return;
    if (meshes.has(id)) throw new Error('Duplicate sceneops_id: ' + id);
    meshes.set(id, node as Mesh);
  });
  const changes: {mesh: Mesh; before: Material | Material[]; after: Material | Material[]}[] = [];
  const generated: Material[] = [];
  const restoreLights: (()=>void)[] = [];
  try {
    for (const object of project.objects) {
      const mesh = meshes.get(object.id);
      if (!mesh) throw new Error('Missing sceneops_id: ' + object.id);
      const originals = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      if (originals.length !== object.materialSlots.length) throw new Error('Material slots changed: ' + object.id);
      const next = originals.map((source, slot) => {
        const binding = object.materialSlots.find(value => value.slot === slot);
        const index = project.materials.findIndex(value => value.id === binding?.materialId);
        if (index < 0) throw new Error('Missing material binding');
        const state = project.materials[index];
        if (requiresUv[index] && !mesh.geometry.getAttribute('uv')) throw new Error('Shader graph requires UV');
        const material = factories[index](undefined, source as MeshPhysicalMaterial);
        generated.push(material);
        material.normalScale.set(state.normalScale, state.normalScale * (material.normalMap && !mesh.geometry.getAttribute('tangent') ? -1 : 1));
        material.transparent = state.alphaMode === 'BLEND' || material.opacityNode !== null;
        material.depthWrite = !material.transparent;
        material.alphaTest = state.alphaMode === 'MASK' ? state.alphaCutoff : 0;
        if (state.colorOverrides?.baseColor === false) material.color.copy((source as MeshPhysicalMaterial).color);
        if (state.colorOverrides?.emissive === false) material.emissive.copy((source as MeshPhysicalMaterial).emissive);
        const effect = state.procedural;
        if (effect.type !== 'none' && !state.shaderGraph) {
          if (!mesh.geometry.getAttribute('uv')) throw new Error('Procedural material requires UV');
          const coordinate = uv().mul(effect.scale);
          const angle = effect.direction * Math.PI / 180;
          const rotated = vec2(coordinate.x.mul(Math.cos(angle)).sub(coordinate.y.mul(Math.sin(angle))), coordinate.x.mul(Math.sin(angle)).add(coordinate.y.mul(Math.cos(angle)))).add(effect.seed * 0.071);
          const pattern = effect.type === 'noise' ? mx_noise_float(rotated).mul(0.5).add(0.5) : effect.type === 'stripes' ? sin(rotated.x.mul(Math.PI * 2)).mul(0.5).add(0.5) : mod(floor(rotated.x).add(floor(rotated.y)), 2);
          const width = 0.47 * (1 - effect.contrast) + 0.015;
          const contrasted = smoothstep(0.5 - width, 0.5 + width, pattern);
          if (effect.target === 'color') material.colorNode = mix(materialColor.rgb, color(effect.secondaryColor), contrasted.mul(effect.strength));
          else material.roughnessNode = clamp(materialRoughness.add(contrasted.sub(0.5).mul(effect.strength)), 0, 1);
        }
        return material;
      });
      changes.push({mesh, before: mesh.material, after: Array.isArray(mesh.material) ? next : next[0]});
    }
    for (const change of changes) change.mesh.material = change.after;
    const sourceLights=new Map<string,Light>();
    root.traverse(node=>{if(node instanceof Light&&typeof node.userData.sceneops_id==='string'){
      if(sourceLights.has(node.userData.sceneops_id))throw new Error('Duplicate source light identity');
      sourceLights.set(node.userData.sceneops_id,node);
    }});
    ${lighting}
    await validate(root);
  } catch (error) {
    restoreLights.reverse().forEach(restore=>restore());
    for (const change of changes) change.mesh.material = change.before;
    generated.forEach(material => material.dispose());
    throw error;
  }
  return () => {
    restoreLights.reverse().forEach(restore=>restore());
    for (const change of changes) if (change.mesh.material === change.after) change.mesh.material = change.before;
    generated.forEach(material => material.dispose());
  };
}
`;
}
