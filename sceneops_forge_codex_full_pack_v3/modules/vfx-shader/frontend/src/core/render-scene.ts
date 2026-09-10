import * as THREE from 'three/webgpu';
import { clamp, color, floor, mix, mod, mx_noise_float, sin, smoothstep, uv, vec2, materialColor, materialRoughness } from 'three/tsl';
import { clone } from 'three/addons/utils/SkeletonUtils.js';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import * as WebGPUTextureUtils from 'three/addons/utils/WebGPUTextureUtils.js';
import type { LookdevProject, MaterialState, LightState } from './lookdev';
import { createDemoProject } from './lookdev';
import { inspectImportedScene, importedAssetMetadata } from './three-lookdev';
import { compileShaderGraph } from './shader-graph-tsl';

export function assertAssetBindings(source: THREE.Object3D, project: LookdevProject) {
  const expected = project.source.kind === 'demo' ? createDemoProject() : inspectImportedScene(source, project.source.fileName);
  const bindings = (p: LookdevProject) => [...p.objects].sort((a, b) => a.id.localeCompare(b.id)).map(o => [o.id, o.materialSlots.map(s => [s.slot, s.sourceMaterialId])]);
  if (JSON.stringify(bindings(expected)) !== JSON.stringify(bindings(project))) throw new Error('工程对象、材质槽或源材质映射与原始模型不匹配。');
}

function cloneAsset(source: THREE.Object3D, project: LookdevProject) {
  assertAssetBindings(source, project);
  let content = clone(source);
  const lights: THREE.Light[] = [];
  const carriers = new Map<number | string, THREE.Object3D>();
  content.traverse(node => {
    if ((node as THREE.Mesh).isMesh) node.userData.lookdevObjectId = node.userData.sceneops_id;
    if ((node as THREE.Light).isLight) lights.push(node as THREE.Light);
  });
  // Keep each light's transform-bearing node and descendants, replacing only its lighting component.
  for (const [lightIndex, light] of lights.entries()) {
    const carrier = new THREE.Object3D().copy(light, false);
    carrier.uuid = light.uuid;
    carriers.set(lightIndex, carrier);
    if (typeof light.userData.sceneops_id === 'string') carriers.set(light.userData.sceneops_id, carrier);
    const parent = light.parent;
    const position = parent?.children.indexOf(light) ?? -1;
    while (light.children.length) carrier.add(light.children[0]);
    if (parent) { parent.remove(light); parent.add(carrier); parent.children.splice(parent.children.indexOf(carrier), 1); parent.children.splice(position, 0, carrier); }
    else content = carrier;
  }
  return { content, carriers };
}

function addProjectLights(scene: THREE.Scene, content: THREE.Object3D, carriers: Map<number | string, THREE.Object3D>, project: LookdevProject, exporting = false) {
  content.updateMatrixWorld(true);
  const used = new Set<number>();
  for (const state of project.lights) {
    if (exporting && (state.type === 'rectArea' || !state.enabled)) continue;
    // Previous packages already used this stable import ID; migrate their missing binding in memory.
    const legacyIndex = project.source.kind === 'glb' && /^import-light-\d+$/.test(state.id) ? Number(state.id.slice('import-light-'.length)) : undefined;
    const index = state.sourceLightIndex ?? legacyIndex;
    const light = makeLight(state);
    if (index === undefined) { scene.add(light); continue; }
    const carrier = /^import-light-\d+$/.test(state.id) ? carriers.get(index) : carriers.get(state.id);
    if (!carrier || used.has(index)) throw new Error('工程源灯光绑定无效或重复。');
    used.add(index);
    const originalPosition = carrier.getWorldPosition(new THREE.Vector3());
    light.position.set(0, 0, 0);
    if (!originalPosition.toArray().every((value, i) => value === state.position[i])) light.position.copy(carrier.worldToLocal(new THREE.Vector3(...state.position)));
    const originalRotation = new THREE.Euler().setFromQuaternion(carrier.getWorldQuaternion(new THREE.Quaternion()));
    light.quaternion.identity();
    if (![originalRotation.x, originalRotation.y, originalRotation.z].every((value, i) => value === state.rotation[i])) {
      // A changed rotation specifies a world-space -Z direction. Use the full inverse linear transform,
      // rather than decomposing a potentially sheared world matrix into another quaternion.
      const worldDirection = new THREE.Vector3(0, 0, -1).applyEuler(new THREE.Euler(...state.rotation));
      const localDirection = worldDirection.transformDirection(carrier.matrixWorld.clone().invert());
      light.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, -1), localDirection);
    }
    light.name = state.name + ' · 光源';
    carrier.add(light);
  }
}

export function applyPhysical(material: THREE.MeshPhysicalMaterial | THREE.MeshPhysicalNodeMaterial, state: MaterialState, normalOrientation = 1) {
  material.name = state.name;
  if (state.colorOverrides?.baseColor ?? ('#' + material.color.getHexString() !== state.baseColor.toLowerCase())) material.color.set(state.baseColor);
  material.metalness = state.metalness;
  material.roughness = state.roughness;
  material.normalScale.set(state.normalScale, state.normalScale * normalOrientation);
  if (state.colorOverrides?.emissive ?? ('#' + material.emissive.getHexString() !== state.emissive.toLowerCase())) material.emissive.set(state.emissive);
  material.emissiveIntensity = state.emissiveIntensity;
  material.opacity = state.opacity;
  material.transmission = state.transmission;
  material.ior = state.ior;
  material.clearcoat = state.clearcoat;
  material.clearcoatRoughness = state.clearcoatRoughness;
  material.transparent = state.alphaMode === 'BLEND';
  material.alphaTest = state.alphaMode === 'MASK' ? state.alphaCutoff : 0;
}

export function nodeMaterial(state: MaterialState, source: THREE.Material, hasUv: boolean, hasTangent = false) {
  const material = new THREE.MeshPhysicalNodeMaterial();
  material.copy(source);
  material.alphaTest = source.alphaTest;
  applyPhysical(material, state, material.normalMap && !hasTangent ? -1 : 1);
  const effect = state.procedural;
  if (effect.type !== 'none') {
    if (!hasUv) throw new Error('这个材质所在网格没有 UV；请先在建模软件中展开 UV。');
    const coordinate = uv().mul(effect.scale);
    const radians = effect.direction * Math.PI / 180;
    const rotated = vec2(
      coordinate.x.mul(Math.cos(radians)).sub(coordinate.y.mul(Math.sin(radians))),
      coordinate.x.mul(Math.sin(radians)).add(coordinate.y.mul(Math.cos(radians))),
    ).add(effect.seed * 0.071);
    const pattern = effect.type === 'noise' ? mx_noise_float(rotated).mul(0.5).add(0.5)
      : effect.type === 'stripes' ? sin(rotated.x.mul(Math.PI * 2)).mul(0.5).add(0.5)
      : mod(floor(rotated.x).add(floor(rotated.y)), 2);
    const width = 0.47 * (1 - effect.contrast) + 0.015;
    const contrasted = smoothstep(0.5 - width, 0.5 + width, pattern);
    if (effect.target === 'color') {
      material.colorNode = mix(materialColor.rgb, color(effect.secondaryColor), contrasted.mul(effect.strength));
    } else {
      material.roughnessNode = clamp(materialRoughness.add(contrasted.sub(0.5).mul(effect.strength)), 0, 1);
    }
  }
  if (state.shaderGraph) {
    const graph = compileShaderGraph(state.shaderGraph, hasUv);
    if (graph.color) material.colorNode = graph.color;
    if (graph.roughness) material.roughnessNode = graph.roughness;
    if (graph.emissive) material.emissiveNode = graph.emissive;
    if (graph.opacity) {
      material.opacityNode = graph.opacity;
      material.transparent = true;
      material.depthWrite = false;
    }
  }
  return material;
}

export function makeLight(state: LightState) {
  const light = state.type === 'directional' ? new THREE.DirectionalLight(state.color, state.intensity)
    : state.type === 'point' ? new THREE.PointLight(state.color, state.intensity, state.distance)
    : state.type === 'spot' ? new THREE.SpotLight(state.color, state.intensity, state.distance, state.angle, state.penumbra)
    : new THREE.RectAreaLight(state.color, state.intensity, state.width, state.height);
  light.name = state.name;
  light.position.fromArray(state.position);
  light.rotation.set(...state.rotation);
  light.visible = state.enabled;
  // Directional/spot lights point along their local -Z, just like area lights.
  if (light instanceof THREE.DirectionalLight || light instanceof THREE.SpotLight) {
    light.target.position.set(0, 0, -1);
    light.add(light.target);
  }
  return light;
}

export type RenderScene = { scene: THREE.Scene; content: THREE.Object3D; dispose(): void };
export function buildRenderScene(source: THREE.Object3D, project: LookdevProject, environment: THREE.Texture | null): RenderScene {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#131920');
  scene.environment = environment;
  scene.environmentIntensity = project.environment.intensity;
  scene.environmentRotation.y = project.environment.rotation;
  const { content, carriers } = cloneAsset(source, project);
  const allocated: THREE.Material[] = [];
  const states = new Map(project.objects.map((o) => [o.id, o]));
  const materials = new Map(project.materials.map((m) => [m.id, m]));
  try {
    content.traverse((node) => {
      if (!(node as THREE.Mesh).isMesh) return;
      const mesh = node as THREE.Mesh;
      const object = states.get(mesh.userData.lookdevObjectId);
      if (!object) throw new Error('工程对象与原始模型不匹配。');
      const originals = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      const result = originals.map((sourceMaterial, index) => {
        const slot = object.materialSlots.find((s) => s.slot === index);
        const state = slot && materials.get(slot.materialId);
        if (!state) throw new Error('工程材质槽与原始模型不匹配。');
        const next = nodeMaterial(state, sourceMaterial, !!mesh.geometry.getAttribute('uv'), !!mesh.geometry.getAttribute('tangent'));
        allocated.push(next);
        return next;
      });
      mesh.material = Array.isArray(mesh.material) ? result : result[0];
    });
  } catch (e) {
    allocated.forEach((m) => m.dispose());
    throw e;
  }
  scene.add(content);
  addProjectLights(scene, content, carriers, project);
  return { scene, content, dispose: () => allocated.forEach((m) => m.dispose()) };
}

export async function exportGlb(source: THREE.Object3D, project: LookdevProject) {
  const scene = new THREE.Scene();
  const { content, carriers } = cloneAsset(source, project);
  const generated: THREE.Material[] = [];
  const shared = new Map<string, Map<string, THREE.MeshPhysicalMaterial>>();
  const alphaStates = new Map<THREE.Material, MaterialState>();
  content.traverse((node) => {
    if (!(node as THREE.Mesh).isMesh) return;
    const mesh = node as THREE.Mesh;
    const object = project.objects.find((o) => o.id === mesh.userData.lookdevObjectId)!;
    const originals = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    const next = originals.map((original, index) => {
      const slot = object.materialSlots.find((s) => s.slot === index)!;
      const state = project.materials.find((m) => m.id === slot.materialId)!;
      const hasTangent = !!mesh.geometry.getAttribute('tangent');
      const sourceVariant = original.uuid + ':' + hasTangent;
      const variants = shared.get(state.id) ?? new Map<string, THREE.MeshPhysicalMaterial>();
      shared.set(state.id, variants);
      const cached = variants.get(sourceVariant);
      if (cached) return cached;
      const material = new THREE.MeshPhysicalMaterial();
      if ((original as THREE.MeshPhysicalMaterial).isMeshPhysicalMaterial) material.copy(original as THREE.MeshPhysicalMaterial);
      else THREE.MeshStandardMaterial.prototype.copy.call(material, original as THREE.MeshStandardMaterial);
      applyPhysical(material, state, material.normalMap && !hasTangent ? -1 : 1);
      material.userData.lookdevSourceMaterialId = slot.sourceMaterialId;
      material.userData.lookdevMaterialId = state.id;
      // glTF supports a signed scalar. Preserve it in the writer hook instead of baking its sign into pixels.
      if (material.normalMap) material.normalScale.set(Math.abs(state.normalScale), Math.abs(state.normalScale) * (hasTangent ? 1 : -1));
      generated.push(material);
      alphaStates.set(material, state);
      variants.set(sourceVariant, material);
      return material;
    });
    mesh.material = Array.isArray(mesh.material) ? next : next[0];
    delete mesh.userData.lookdevObjectId;
  });
  scene.add(content);
  addProjectLights(scene, content, carriers, project, true);
  try {
    return await new GLTFExporter().register(writer => ({
      afterParse: () => {
        const metadata = importedAssetMetadata.get(source);
        const asset = (writer as typeof writer & { json: { asset: { extras?: Record<string, unknown>; copyright?: string } } }).json.asset;
        if (metadata?.extras) asset.extras = structuredClone(metadata.extras);
        if (metadata?.copyright) asset.copyright = metadata.copyright;
      },
      writeMaterialAsync: async (material, definition) => {
        const state = alphaStates.get(material)!;
        if (definition.normalTexture) (definition.normalTexture as { scale?: number }).scale = state.normalScale;
        definition.alphaMode = state.alphaMode;
        if (state.alphaMode === 'MASK') definition.alphaCutoff = state.alphaCutoff;
        else delete definition.alphaCutoff;
      },
    })).setTextureUtils(WebGPUTextureUtils).parseAsync(scene, {
      binary: true, onlyVisible: false, animations: source.animations, trs: source.animations.length > 0,
    }) as ArrayBuffer;
  } finally { generated.forEach((m) => m.dispose()); }
}

export function disposeAsset(root: THREE.Object3D) {
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();
  root.traverse((node) => {
    const mesh = node as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.geometry.dispose();
    (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).forEach((m) => materials.add(m));
  });
  materials.forEach((m) => {
    Object.values(m).forEach((value) => { if (value instanceof THREE.Texture) textures.add(value); });
    m.dispose();
  });
  const images = new Set<unknown>();
  textures.forEach((t) => { images.add(t.source.data); t.dispose(); });
  images.forEach(image => { if (typeof ImageBitmap !== 'undefined' && image instanceof ImageBitmap) image.close(); });
}
