type GltfPrimitive = { mode?: number; material?: number; [key: string]: unknown };
type GltfResource = { uri?: string };
type GltfMaterial = {
  alphaMode?: string;
  alphaCutoff?: number;
  pbrMetallicRoughness: { metallicFactor?: number; roughnessFactor?: number; [key: string]: unknown };
  extensions?: Record<string, unknown>;
  [key: string]: unknown;
};

export type GltfContainer = {
  scenes: unknown[];
  nodes: unknown[];
  meshes: Array<{ primitives: GltfPrimitive[]; [key: string]: unknown }>;
  materials: GltfMaterial[];
  images?: GltfResource[];
  buffers?: GltfResource[];
  extensionsUsed?: unknown[];
  extensionsRequired?: unknown[];
  [key: string]: unknown;
};

// This is the intersection of what the loader can read, the editor can retain,
// and the exporter can write back with the same scene meaning.
export const GLTF_ASSET_POLICY = {
  preservedRequiredExtensions: [
    'EXT_mesh_gpu_instancing',
    'KHR_lights_punctual',
    'KHR_materials_anisotropy',
    'KHR_materials_clearcoat',
    'KHR_materials_dispersion',
    'KHR_materials_emissive_strength',
    'KHR_materials_ior',
    'KHR_materials_iridescence',
    'KHR_materials_sheen',
    'KHR_materials_specular',
    'KHR_materials_transmission',
    'KHR_materials_volume',
    'KHR_mesh_quantization',
    'KHR_texture_transform',
  ],
  decodedToStandard: ['EXT_meshopt_compression', 'KHR_draco_mesh_compression'],
  rejectedExtensions: ['KHR_materials_unlit', 'KHR_texture_basisu'],
  trianglePrimitiveModes: [4, 5, 6],
  maxScenes: 1,
} as const;

const supportedRequiredExtensions = new Set<string>([
  ...GLTF_ASSET_POLICY.preservedRequiredExtensions,
  ...GLTF_ASSET_POLICY.decodedToStandard,
]);
const rejectedExtensions = new Set<string>(GLTF_ASSET_POLICY.rejectedExtensions);
const trianglePrimitiveModes = new Set<number>(GLTF_ASSET_POLICY.trianglePrimitiveModes);

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

export function assertSupportedGltf(json: GltfContainer): void {
  const errors: string[] = [];
  if (json.scenes.length > GLTF_ASSET_POLICY.maxScenes) {
    errors.push('此版一次只支持一个 glTF 场景；请在建模软件中合并需要的内容后重新导入。');
  }
  for (const mesh of json.meshes) for (const primitive of mesh.primitives) {
    if (!trianglePrimitiveModes.has(primitive.mode ?? 4)) {
      errors.push('此版只支持三角形网格，不支持点／线图元；请在建模软件中转换后重新导入。');
      break;
    }
  }
  if ([...(json.images ?? []), ...(json.buffers ?? [])].some((item) => item.uri && !item.uri.startsWith('data:'))) {
    errors.push('请选择贴图与缓冲数据全部内嵌的 GLB，不能包含外部资源链接。');
  }
  const used = new Set(stringList(json.extensionsUsed));
  if (used.has('KHR_texture_basisu')) errors.push('此版暂不支持 KTX2 压缩贴图，请导出 PNG/JPEG 内嵌贴图 GLB。');
  if (used.has('KHR_materials_unlit')) errors.push('此版编辑物理材质，请将 Unlit 材质转换为 PBR 后导入。');
  const unsupportedRequired = stringList(json.extensionsRequired)
    .filter((extension) => !supportedRequiredExtensions.has(extension) && !rejectedExtensions.has(extension));
  if (unsupportedRequired.length) {
    errors.push(`这个 GLB 依赖当前版本不支持的必需扩展：${unsupportedRequired.join('、')}。请关闭这些扩展，或转换为标准 PBR GLB。`);
  }
  if (errors.length) throw new Error([...new Set(errors)].join(' '));
}
