import { z } from 'zod/v4';
import { patchShaderGraphParameters, shaderGraphSchema, type ShaderGraph, type ShaderParameterValue } from './shader-graph';

export const PROJECT_VERSION = 1 as const;
const color = z.string().regex(/^#[0-9a-fA-F]{6}$/, '颜色须为 #RRGGBB');
const unit = z.number().min(0).max(1);
const vector = z.tuple([z.number(), z.number(), z.number()]);
export const effectSchema = z.object({
  type: z.enum(['none', 'noise', 'stripes', 'checker']),
  target: z.enum(['color', 'roughness']),
  scale: z.number().min(0.1).max(100),
  direction: z.number().min(0).max(360),
  contrast: unit, seed: z.number().int().min(0).max(9999), strength: unit,
  secondaryColor: color,
}).strict();
const materialFields = {
  baseColor: color, metalness: unit, roughness: unit,
  normalScale: z.number(), emissive: color,
  emissiveIntensity: z.number().min(0), opacity: unit, transmission: unit,
  alphaMode: z.enum(['OPAQUE', 'MASK', 'BLEND']), alphaCutoff: z.number().min(0),
  ior: z.union([z.literal(0), z.number().min(1)]), clearcoat: unit, clearcoatRoughness: unit,
};
export const materialSchema = z.preprocess((input) => {
  if (input && typeof input === 'object' && !('alphaMode' in input)) {
    const old = input as Record<string, unknown>;
    return { ...old, alphaMode: typeof old.opacity === 'number' && old.opacity < 1 ? 'BLEND' : 'OPAQUE', alphaCutoff: 0.5 };
  }
  return input;
}, z.object({
  id: z.string().min(1), name: z.string().min(1), ...materialFields, procedural: effectSchema,
  shaderGraph: shaderGraphSchema.nullable().default(null),
  colorOverrides: z.object({ baseColor: z.boolean().optional(), emissive: z.boolean().optional() }).strict().optional(),
}).strict());
const lightFields = {
  color, intensity: z.number().min(0), position: vector, rotation: vector,
  distance: z.number().min(0), angle: z.number().positive().max(Math.PI / 2),
  penumbra: unit, width: z.number().positive(), height: z.number().positive(),
  enabled: z.boolean(),
};
export const lightSchema = z.object({
  id: z.string().min(1), name: z.string().min(1),
  sourceLightIndex: z.number().int().nonnegative().optional(),
  type: z.enum(['directional', 'point', 'spot', 'rectArea']), ...lightFields,
}).strict();
const environmentSchema = z.object({
  intensity: z.number().min(0).max(4), rotation: z.number().min(-Math.PI).max(Math.PI),
}).strict();
const notEmpty = (value: object) => Object.keys(value).length > 0;
export const operationSchema = z.discriminatedUnion('kind', [
  z.object({ kind: z.literal('material.update'), targetId: z.string(), patch: z.object(materialFields).partial().strict().refine(notEmpty) }).strict(),
  z.object({ kind: z.literal('material.effect.set'), targetId: z.string(), effect: effectSchema }).strict(),
  z.object({ kind: z.literal('material.graph.set'), targetId: z.string(), graph: shaderGraphSchema }).strict(),
  z.object({ kind: z.literal('material.graph.patch'), targetId: z.string(), parameters: z.record(z.string(), z.union([z.number(), color])).refine(notEmpty) }).strict(),
  z.object({ kind: z.literal('material.graph.clear'), targetId: z.string() }).strict(),
  z.object({ kind: z.literal('light.update'), targetId: z.string(), patch: z.object(lightFields).partial().strict().refine(notEmpty) }).strict(),
  z.object({ kind: z.literal('light.add'), light: lightSchema.omit({ sourceLightIndex: true }) }).strict(),
  z.object({ kind: z.literal('environment.update'), patch: environmentSchema.partial().strict().refine(notEmpty) }).strict(),
]);
export const editResponseSchema = z.object({
  status: z.enum(['applied', 'declined', 'noop']).optional(),
  summary: z.string().trim().min(1).max(1000),
  operations: z.array(operationSchema).max(16),
}).strict().transform(value => ({ ...value, status: value.status ?? (value.operations.length ? 'applied' : 'noop') }))
  .refine(value => (value.status === 'applied') === (value.operations.length > 0), '只有 applied 可以包含修改操作。');
export const projectSchema = z.object({
  version: z.literal(PROJECT_VERSION), revision: z.number().int().min(0),
  name: z.string().min(1).max(200),
  source: z.discriminatedUnion('kind', [
    z.object({ kind: z.literal('demo') }).strict(),
    z.object({ kind: z.literal('glb'), fileName: z.string().min(1) }).strict(),
  ]),
  objects: z.array(z.object({
    id: z.string().min(1), name: z.string(), parentName: z.string(),
    materialSlots: z.array(z.object({
      slot: z.number().int().min(0), materialId: z.string(), sourceMaterialId: z.string(),
    }).strict()).min(1),
  }).strict()).min(1),
  materials: z.array(materialSchema).min(1), lights: z.array(lightSchema),
  environment: environmentSchema,
  view: z.object({ position: vector, target: vector }).strict(),
  editLog: z.array(z.object({
    id: z.string(), at: z.string(), source: z.enum(['manual', 'ai']),
    summary: z.string(), operations: z.array(operationSchema),
  }).strict()),
}).strict();

export type ProceduralEffect = z.infer<typeof effectSchema>;
export type ProceduralType = ProceduralEffect['type'];
export type ProceduralTarget = ProceduralEffect['target'];
export type MaterialState = z.infer<typeof materialSchema>;
export type MaterialPatch = Partial<Omit<MaterialState, 'id' | 'name' | 'procedural' | 'shaderGraph' | 'colorOverrides'>>;
export type { ShaderGraph, ShaderParameterValue };
export type LightState = z.infer<typeof lightSchema>;
export type LightType = LightState['type'];
export type LightPatch = Partial<Omit<LightState, 'id' | 'name' | 'type'>>;
export type LookdevProject = z.infer<typeof projectSchema>;
export type SceneObjectState = LookdevProject['objects'][number];
export type LookdevOperation = z.infer<typeof operationSchema>;
export type EditResponse = z.infer<typeof editResponseSchema>;
export type EditLogEntry = LookdevProject['editLog'][number];
export type Selection = { objectId: string; slot: number };
export type EditScope = { materialIds: string[]; lightIds: string[]; lighting: boolean };

export const DEFAULT_EFFECT: ProceduralEffect = {
  type: 'none', target: 'roughness', scale: 8, direction: 0, contrast: 0.55,
  seed: 1, strength: 0.22, secondaryColor: '#6d8799',
};
export function createMaterial(id: string, name: string, values: Partial<MaterialState> = {}): MaterialState {
  return {
    id, name, baseColor: '#8a929c', metalness: 0, roughness: 0.55, normalScale: 1,
    emissive: '#000000', emissiveIntensity: 0, opacity: 1, transmission: 0, ior: 1.5,
    alphaMode: values.opacity !== undefined && values.opacity < 1 ? 'BLEND' : 'OPAQUE', alphaCutoff: 0.5,
    clearcoat: 0, clearcoatRoughness: 0.15, colorOverrides: { baseColor: true, emissive: true }, ...values,
    procedural: { ...DEFAULT_EFFECT, ...values.procedural },
    shaderGraph: values.shaderGraph ?? null,
  };
}
export function createLight(type: LightType, id: string, name: string): LightState {
  return {
    id, name, type, color: '#e7f3ff', intensity: type === 'spot' || type === 'point' ? 30 : 5,
    position: [-3.5, 4.5, 4.5], rotation: [-0.55, -0.5, 0],
    distance: 0, angle: 0.7, penumbra: 0.4, width: 4, height: 3, enabled: true,
  };
}
export function createDemoProject(): LookdevProject {
  return {
    version: 1, revision: 0, name: '产品外观探索 01', source: { kind: 'demo' },
    objects: [
      ['shell', '产品外壳'], ['glass', '玻璃面板'], ['rubber', '底部橡胶'],
    ].map(([id, name]) => ({
      id: 'demo-' + id, name, parentName: '演示产品',
      materialSlots: [{ slot: 0, materialId: 'mat-' + id, sourceMaterialId: 'mat-' + id }],
    })),
    materials: [
      createMaterial('mat-shell', '深蓝金属', { baseColor: '#183650', metalness: 0.86, roughness: 0.42, clearcoat: 0.12 }),
      createMaterial('mat-glass', '透明玻璃', { baseColor: '#b6d6df', roughness: 0.08, transmission: 0.92, ior: 1.46 }),
      createMaterial('mat-rubber', '深色橡胶', { baseColor: '#15181b', roughness: 0.88 }),
    ],
    lights: [
      createLight('rectArea', 'light-key', '主柔光'),
      { ...createLight('spot', 'light-rim', '轮廓光'), color: '#63e1cb', position: [3.6, 3.6, -3], rotation: [-2.55, 0.72, 0], intensity: 70 },
    ],
    environment: { intensity: 0.72, rotation: 0 },
    view: { position: [5, 3.9, 6.7], target: [0, 1.65, 0] }, editLog: [],
  };
}

export function parseProject(input: unknown): LookdevProject {
  const project = projectSchema.parse(input);
  for (const items of [project.objects, project.materials, project.lights]) {
    if (new Set(items.map((item) => item.id)).size !== items.length) throw new Error('工程包含重复 ID。');
  }
  const ids = new Set(project.materials.map((m) => m.id));
  for (const object of project.objects) {
    if (new Set(object.materialSlots.map((s) => s.slot)).size !== object.materialSlots.length) throw new Error('材质槽重复。');
    for (const slot of object.materialSlots) {
      if (!ids.has(slot.materialId) || !ids.has(slot.sourceMaterialId)) throw new Error('工程材质引用不存在。');
    }
  }
  return project;
}
export function selectedMaterial(project: LookdevProject, selection: Selection) {
  const slot = project.objects.find((o) => o.id === selection.objectId)?.materialSlots.find((s) => s.slot === selection.slot);
  return project.materials.find((m) => m.id === slot?.materialId);
}
export function validateOperations(project: LookdevProject, input: unknown, scope?: EditScope): LookdevOperation[] {
  const operations = z.array(operationSchema).min(1).max(16).parse(input);
  const materials = new Set(project.materials.map((m) => m.id));
  const lights = new Set(project.lights.map((l) => l.id));
  const replacedEffects = new Set<string>();
  for (const op of operations) {
    if (scope && op.kind === 'material.update') {
      z.object({ normalScale: z.number().min(0).max(4), emissiveIntensity: z.number().min(0).max(20), ior: z.number().min(1).max(2.333) }).partial().parse(op.patch);
    }
    if (scope && (op.kind === 'light.update' || op.kind === 'light.add')) {
      const fields = op.kind === 'light.add' ? op.light : op.patch;
      z.object({ intensity: z.number().min(0).max(200), distance: z.number().min(0).max(100), width: z.number().min(0.01).max(50), height: z.number().min(0.01).max(50) }).partial().parse(fields);
    }
    if (
      op.kind === 'material.update' || op.kind === 'material.effect.set' || op.kind === 'material.graph.set'
      || op.kind === 'material.graph.patch' || op.kind === 'material.graph.clear'
    ) {
      if (!materials.has(op.targetId)) throw new Error('材质目标不存在。');
      if (scope && !scope.materialIds.includes(op.targetId)) throw new Error('AI 尝试修改选择范围之外的材质。');
      if (op.kind === 'material.effect.set') {
        if (replacedEffects.has(op.targetId)) throw new Error('同一事务不能重复替换快速效果；组合效果请使用材质图。');
        replacedEffects.add(op.targetId);
      }
      if (op.kind === 'material.graph.patch') {
        const material = project.materials.find((item) => item.id === op.targetId)!;
        patchShaderGraphParameters(material.shaderGraph, op.parameters as Record<string, ShaderParameterValue>);
      }
    } else if (op.kind === 'light.update') {
      if (!lights.has(op.targetId)) throw new Error('灯光目标不存在。');
      if (scope && (!scope.lighting || !scope.lightIds.includes(op.targetId))) throw new Error('灯光不在本次编辑范围内。');
    } else if (op.kind === 'light.add') {
      if (scope && !scope.lighting) throw new Error('本次未允许灯光编辑。');
      if (lights.has(op.light.id)) throw new Error('灯光 ID 已存在。');
      lights.add(op.light.id);
    } else if (scope && !scope.lighting) throw new Error('本次未允许环境编辑。');
  }
  return operations;
}
export function applyOperations(project: LookdevProject, input: unknown, source: 'manual' | 'ai', summary: string): LookdevProject {
  const operations = validateOperations(project, input);
  const next = { ...structuredClone({ ...project, editLog: [] }), editLog: [...project.editLog] };
  for (const op of operations) {
    if (op.kind === 'material.update') {
      const material = next.materials.find((m) => m.id === op.targetId)!;
      if (op.patch.baseColor !== undefined || op.patch.emissive !== undefined) {
        material.colorOverrides = {
          ...material.colorOverrides,
          ...(op.patch.baseColor !== undefined ? { baseColor: true } : {}),
          ...(op.patch.emissive !== undefined ? { emissive: true } : {}),
        };
      }
      if (op.patch.opacity !== undefined && op.patch.opacity < 1 && material.alphaMode === 'OPAQUE' && op.patch.alphaMode === undefined) material.alphaMode = 'BLEND';
      Object.assign(material, op.patch);
    }
    else if (op.kind === 'material.effect.set') next.materials.find((m) => m.id === op.targetId)!.procedural = structuredClone(op.effect);
    else if (op.kind === 'material.graph.set') next.materials.find((m) => m.id === op.targetId)!.shaderGraph = structuredClone(op.graph);
    else if (op.kind === 'material.graph.patch') {
      const material = next.materials.find((m) => m.id === op.targetId)!;
      material.shaderGraph = patchShaderGraphParameters(material.shaderGraph, op.parameters as Record<string, ShaderParameterValue>);
    }
    else if (op.kind === 'material.graph.clear') next.materials.find((m) => m.id === op.targetId)!.shaderGraph = null;
    else if (op.kind === 'light.update') Object.assign(next.lights.find((l) => l.id === op.targetId)!, op.patch);
    else if (op.kind === 'light.add') next.lights.push(structuredClone(op.light));
    else Object.assign(next.environment, op.patch);
  }
  next.revision++;
  next.editLog.push({
    id: crypto.randomUUID(), at: new Date().toISOString(), source, summary,
    operations: structuredClone(operations),
  });
  return next;
}
export function isolateMaterialSlot(project: LookdevProject, objectId: string, slotIndex: number) {
  const slot = project.objects.find((o) => o.id === objectId)?.materialSlots.find((s) => s.slot === slotIndex);
  if (!slot) throw new Error('材质槽不存在。');
  const uses = project.objects.flatMap((o) => o.materialSlots).filter((s) => s.materialId === slot.materialId).length;
  if (uses === 1) return { project, materialId: slot.materialId, isolated: false };
  const next = structuredClone(project);
  const original = next.materials.find((m) => m.id === slot.materialId)!;
  const materialId = crypto.randomUUID();
  next.materials.push({ ...structuredClone(original), id: materialId, name: original.name + '（局部）' });
  next.objects.find((o) => o.id === objectId)!.materialSlots.find((s) => s.slot === slotIndex)!.materialId = materialId;
  return { project: next, materialId, isolated: true };
}
export function getExportWarnings(project: LookdevProject) {
  const used = new Set(project.objects.flatMap((o) => o.materialSlots.map((s) => s.materialId)));
  const warnings: string[] = [];
  if (project.materials.some((m) => used.has(m.id) && (m.procedural.type !== 'none' || m.shaderGraph))) warnings.push('程序化表面与 Shader 图无法写入标准 GLB。');
  if (project.lights.some((l) => l.enabled && l.type === 'rectArea')) warnings.push('矩形面积光无法写入标准 GLB。');
  if (project.environment.intensity !== 0 || project.environment.rotation !== 0) warnings.push('环境照明与旋转无法写入标准 GLB。');
  return warnings;
}
export function summarizeScene(project: LookdevProject) {
  return { revision: project.revision, objects: project.objects, materials: project.materials, lights: project.lights, environment: project.environment };
}
