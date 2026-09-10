import * as THREE from 'three/webgpu';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import {
  createDemoProject,
  createMaterial,
  type LightState,
  type LookdevProject,
  type MaterialState,
  type SceneObjectState,
} from './lookdev';
import { assertSupportedGltf, type GltfContainer } from './gltf-capabilities';
export const importedAssetMetadata = new WeakMap<THREE.Object3D, { extras?: Record<string, unknown>; copyright?: string }>();
const importedMaterialDefinitions = new WeakMap<THREE.Material, unknown>();
const importedAlpha = new WeakMap<THREE.Material, Pick<MaterialState, 'alphaMode' | 'alphaCutoff'>>();

export function inspectGlbContainer(bytes: ArrayBuffer) {
  if (bytes.byteLength < 20) throw new Error('不是有效的 GLB 文件。');
  const view = new DataView(bytes);
  if (view.getUint32(0, true) !== 0x46546c67 || view.getUint32(4, true) !== 2 || view.getUint32(8, true) !== bytes.byteLength) throw new Error('需要完整的 glTF 2.0 二进制文件。');
  const length = view.getUint32(12, true);
  if (view.getUint32(16, true) !== 0x4e4f534a || length + 20 > bytes.byteLength) throw new Error('GLB 场景数据损坏。');
  const parsed = JSON.parse(new TextDecoder().decode(new Uint8Array(bytes, 20, length))) as Partial<GltfContainer>;
  const json = {
    ...parsed,
    scenes: parsed.scenes ?? [],
    nodes: parsed.nodes ?? [],
    meshes: parsed.meshes ?? [],
    materials: parsed.materials ?? [],
  } as GltfContainer;
  assertSupportedGltf(json);
  return json;
}

export async function loadGlbScene(bytes: ArrayBuffer): Promise<THREE.Object3D> {
  inspectGlbContainer(bytes);
  const decoder = new DRACOLoader().setDecoderPath('/draco/');
  try {
    const manager = new THREE.LoadingManager();
    let resourceFailed = false;
    manager.onError = () => { resourceFailed = true; };
    const loader = new GLTFLoader(manager).setDRACOLoader(decoder).setMeshoptDecoder(MeshoptDecoder);
    const gltf = await loader.parseAsync(bytes.slice(0), '');
    if (resourceFailed) throw new Error('模型中的贴图未能解码；请修复贴图后重新导入。');
    gltf.scene.animations = gltf.animations;
    importedAssetMetadata.set(gltf.scene, structuredClone(gltf.parser.json.asset));
    for (const [object, association] of gltf.parser.associations) {
      const reference = association as typeof association & { primitives?: number };
      if ((object as THREE.Mesh).isMesh && reference.meshes !== undefined && reference.primitives !== undefined) {
        const definition = gltf.parser.json.meshes[reference.meshes];
        if (definition.primitives.length > 1) {
          const primitiveId = definition.primitives[reference.primitives].extras?.sceneops_id;
          if (primitiveId) {
            const mesh = object as THREE.Object3D;
            const ownerId = mesh.parent?.userData.sceneops_id;
            if (typeof ownerId !== 'string') throw new Error('多图元网格缺少所属节点的稳定身份。');
            mesh.userData.sceneops_id = `${ownerId}:${primitiveId}`;
          }
        }
      }
      if (reference?.materials === undefined) continue;
      const definition = gltf.parser.json.materials[reference.materials];
      const sourceId = definition.extras?.lookdevSourceMaterialId;
      if (typeof sourceId !== 'string' || !sourceId.trim() || sourceId !== sourceId.trim()) throw new Error('模型材质缺少持久的 lookdevSourceMaterialId；请通过资产来源接口建立材质身份后重试。');
      (object as THREE.Material).userData.lookdevSourceMaterialId = sourceId;
      if (definition.extras.lookdevMaterialId !== undefined) (object as THREE.Material).userData.lookdevMaterialId = definition.extras.lookdevMaterialId;
      importedMaterialDefinitions.set(object as THREE.Material, structuredClone(definition));
      importedAlpha.set(object as THREE.Material, { alphaMode: definition.alphaMode ?? 'OPAQUE', alphaCutoff: definition.alphaCutoff ?? 0.5 });
    }
    return gltf.scene;
  } finally { decoder.dispose(); }
}

function materialToState(id: string, material: THREE.Material, index: number): MaterialState {
  const source = material as THREE.MeshPhysicalMaterial;
  return createMaterial(id, material.name || `材质 ${index + 1}`, {
    colorOverrides: { baseColor: false, emissive: false },
    baseColor: source.color?.getHexString ? `#${source.color.getHexString()}` : '#8a929c',
    metalness: typeof source.metalness === 'number' ? source.metalness : 0,
    roughness: typeof source.roughness === 'number' ? source.roughness : 0.55,
    normalScale: source.normalScale?.x ?? 1,
    emissive: source.emissive?.getHexString ? `#${source.emissive.getHexString()}` : '#000000',
    emissiveIntensity: typeof source.emissiveIntensity === 'number' ? source.emissiveIntensity : 0,
    opacity: typeof source.opacity === 'number' ? source.opacity : 1,
    alphaMode: importedAlpha.get(material)?.alphaMode ?? (source.transparent ? 'BLEND' : source.alphaTest > 0 ? 'MASK' : 'OPAQUE'),
    alphaCutoff: importedAlpha.get(material)?.alphaCutoff ?? (source.alphaTest > 0 ? source.alphaTest : 0.5),
    transmission: typeof source.transmission === 'number' ? source.transmission : 0,
    ior: typeof source.ior === 'number' ? source.ior : 1.5,
    clearcoat: typeof source.clearcoat === 'number' ? source.clearcoat : 0,
    clearcoatRoughness: typeof source.clearcoatRoughness === 'number' ? source.clearcoatRoughness : 0.15,
  });
}

function lightToState(light: THREE.Light, index: number): LightState | null {
  let type: LightState['type'];
  if ((light as THREE.DirectionalLight).isDirectionalLight) type = 'directional';
  else if ((light as THREE.SpotLight).isSpotLight) type = 'spot';
  else if ((light as THREE.PointLight).isPointLight) type = 'point';
  else if ((light as THREE.RectAreaLight).isRectAreaLight) type = 'rectArea';
  else return null;

  const source = light as THREE.SpotLight & { width?: number; height?: number };
  const position = light.getWorldPosition(new THREE.Vector3());
  const rotation = new THREE.Euler().setFromQuaternion(light.getWorldQuaternion(new THREE.Quaternion()));
  return {
    id: light.userData.sceneops_id ?? `import-light-${index}`,
    sourceLightIndex: index,
    name: light.name || `灯光 ${index + 1}`,
    type,
    color: `#${light.color.getHexString()}`,
    intensity: light.intensity,
    position: position.toArray() as [number, number, number],
    rotation: [rotation.x, rotation.y, rotation.z],
    distance: source.distance ?? 0,
    angle: source.angle ?? 0.7,
    penumbra: source.penumbra ?? 0.35,
    width: source.width ?? 2,
    height: source.height ?? 2,
    enabled: light.visible,
  };
}

function sameMaterialContent(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (Array.isArray(left) || Array.isArray(right)) return Array.isArray(left) && Array.isArray(right) && left.length === right.length && left.every((value, index) => sameMaterialContent(value, right[index]));
  if (!left || !right || typeof left !== 'object' || typeof right !== 'object') return false;
  const a = left as Record<string, unknown>, b = right as Record<string, unknown>;
  const keys = Object.keys(a);
  return keys.length === Object.keys(b).length && keys.every(key => Object.hasOwn(b, key) && sameMaterialContent(a[key], b[key]));
}

export function inspectImportedScene(scene: THREE.Object3D, fileName: string): LookdevProject {
  scene.traverse(node => {
    if ((node as THREE.Points).isPoints || (node as THREE.Line).isLine) throw new Error('此版只支持三角形网格，不支持点／线图元。');
  });
  const objects: SceneObjectState[] = [];
  const materials: MaterialState[] = [];
  const importedMaterials = new Map<string, { state: MaterialState; definition: unknown }>();
  const lights: LightState[] = [];
  let meshIndex = 0;
  const objectIds = new Set<string>();
  let lightIndex = 0;

  scene.traverse((node) => {
    if ((node as THREE.Mesh).isMesh) {
      const mesh = node as THREE.Mesh;
      meshIndex++;
      const objectId = mesh.userData.sceneops_id;
      if (typeof objectId !== 'string' || !objectId.trim() || objectId !== objectId.trim()) throw new Error('模型网格缺少有效的 sceneops_id；请在资产导入流程中建立稳定身份后重试。');
      if (objectIds.has(objectId)) throw new Error(`模型包含重复 sceneops_id：${objectId}`);
      objectIds.add(objectId);
      const sourceMaterials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      const materialSlots = sourceMaterials.map((material, slot) => {
        if (!(material as THREE.MeshStandardMaterial).isMeshStandardMaterial) throw new Error('此版只支持标准 PBR 材质。');
        const sourceMaterialId = material.userData.lookdevSourceMaterialId;
        const materialId = material.userData.lookdevMaterialId ?? sourceMaterialId;
        if (typeof sourceMaterialId !== 'string' || !sourceMaterialId.trim() || sourceMaterialId !== sourceMaterialId.trim() || typeof materialId !== 'string' || !materialId.trim() || materialId !== materialId.trim()) throw new Error('模型材质缺少有效的持久身份；请先通过资产来源接口建立材质绑定。');
        const state = materialToState(materialId, material, materials.length);
        const definition = importedMaterialDefinitions.get(material);
        const previous = importedMaterials.get(materialId);
        if (previous) {
          const values = ({ name: _name, ...rest }: MaterialState) => rest;
          if (!sameMaterialContent(values(previous.state), values(state)) || (previous.definition !== undefined && definition !== undefined && !sameMaterialContent(previous.definition, definition))) throw new Error(`相同材质身份包含冲突内容：${materialId}`);
        } else {
          importedMaterials.set(materialId, { state, definition });
          materials.push(state);
        }
        return { slot, materialId, sourceMaterialId };
      });
      objects.push({
        id: objectId,
        name: mesh.name || `网格 ${meshIndex}`,
        parentName: mesh.parent?.name || '模型',
        materialSlots,
      });
    } else if ((node as THREE.Light).isLight) {
      const importedLight = lightToState(node as THREE.Light, lightIndex++);
      if (importedLight) lights.push(importedLight);
    }
  });

  if (objects.length === 0) throw new Error('这个 GLB 中没有可编辑的网格对象。');
  const bounds = new THREE.Box3().setFromObject(scene);
  const center = bounds.getCenter(new THREE.Vector3());
  const size = bounds.getSize(new THREE.Vector3());
  const radius = Math.max(size.x, size.y, size.z, 0.5);
  const defaults = createDemoProject();

  return {
    version: 1,
    revision: 0,
    name: fileName.replace(/\.glb$/i, '') || '导入工程',
    source: { kind: 'glb', fileName },
    objects,
    materials,
    lights: lights.length ? lights : defaults.lights,
    environment: { intensity: 0.72, rotation: 0 },
    view: {
      position: [center.x + radius * 1.3, center.y + radius * 0.7, center.z + radius * 1.7],
      target: [center.x, center.y, center.z],
    },
    editLog: [],
  };
}

function placeholderMaterial(name: string, id: string) {
  const material = new THREE.MeshStandardMaterial({ color: 0x777777 });
  material.name = name;
  material.userData.lookdevSourceMaterialId = id;
  return material;
}

export function createDemoScene(): THREE.Group {
  const root = new THREE.Group();
  root.name = '演示产品';

  const shell = new THREE.Mesh(
    new RoundedBoxGeometry(2.65, 3.15, 0.92, 7, 0.24),
    placeholderMaterial('深蓝金属', 'mat-shell'),
  );
  shell.name = '产品外壳';
  shell.position.y = 1.75;
  shell.userData.sceneops_id = 'demo-shell';
  root.add(shell);

  const glass = new THREE.Mesh(
    new RoundedBoxGeometry(2.18, 2.22, 0.07, 5, 0.16),
    placeholderMaterial('透明玻璃', 'mat-glass'),
  );
  glass.name = '玻璃面板';
  glass.position.set(0, 1.92, 0.49);
  glass.userData.sceneops_id = 'demo-glass';
  root.add(glass);

  const rubber = new THREE.Mesh(
    new RoundedBoxGeometry(2.38, 0.28, 0.78, 5, 0.12),
    placeholderMaterial('深色橡胶', 'mat-rubber'),
  );
  rubber.name = '底部橡胶';
  rubber.position.set(0, 0.18, 0);
  rubber.userData.sceneops_id = 'demo-rubber';
  root.add(rubber);

  return root;
}
