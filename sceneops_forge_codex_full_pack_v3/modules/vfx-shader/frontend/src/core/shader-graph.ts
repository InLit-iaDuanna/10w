import { z } from 'zod/v4';

const colorValue = z.string().regex(/^#[0-9a-fA-F]{6}$/, '颜色须为 #RRGGBB');
const graphId = z.string().trim().regex(/^[A-Za-z][A-Za-z0-9_-]{0,47}$/, '节点 ID 只能包含字母、数字、_ 或 -');
const parameterKey = z.string().trim().regex(/^[a-z][A-Za-z0-9_]{0,39}$/, '参数键须以小写字母开头');
const reference = graphId;
const base = { id: graphId };

const floatParameterSchema = z.object({
  ...base,
  kind: z.literal('parameter.float'),
  key: parameterKey,
  label: z.string().trim().min(1).max(40),
  value: z.number().min(-1000).max(1000),
  min: z.number().min(-1000).max(1000),
  max: z.number().min(-1000).max(1000),
}).strict().refine((node) => node.min <= node.value && node.value <= node.max, '浮点参数必须位于 min 和 max 之间。');

const shaderNodeSchema = z.discriminatedUnion('kind', [
  z.object({ ...base, kind: z.enum([
    'input.uv', 'input.positionLocal', 'input.normalView', 'input.viewDirection', 'input.time',
    'input.materialColor', 'input.materialRoughness', 'input.materialEmissive', 'input.materialOpacity',
  ]) }).strict(),
  z.object({ ...base, kind: z.literal('value.float'), value: z.number().min(-1000).max(1000) }).strict(),
  z.object({ ...base, kind: z.literal('value.color'), value: colorValue }).strict(),
  floatParameterSchema,
  z.object({ ...base, kind: z.literal('parameter.color'), key: parameterKey, label: z.string().trim().min(1).max(40), value: colorValue }).strict(),
  z.object({ ...base, kind: z.literal('vector.component'), input: reference, component: z.enum(['x', 'y', 'z']) }).strict(),
  z.object({ ...base, kind: z.literal('vector.rotate2d'), input: reference, angle: reference }).strict(),
  z.object({ ...base, kind: z.enum(['math.add', 'math.subtract', 'math.multiply', 'math.divide', 'math.dot', 'math.mod']), a: reference, b: reference }).strict(),
  z.object({ ...base, kind: z.enum(['math.sin', 'math.abs', 'math.fract', 'math.floor', 'math.oneMinus']), input: reference }).strict(),
  z.object({ ...base, kind: z.literal('math.pow'), base: reference, exponent: reference }).strict(),
  z.object({ ...base, kind: z.literal('math.mix'), a: reference, b: reference, factor: reference }).strict(),
  z.object({ ...base, kind: z.literal('math.smoothstep'), edge0: reference, edge1: reference, input: reference }).strict(),
  z.object({ ...base, kind: z.literal('math.clamp'), input: reference, min: reference, max: reference }).strict(),
  z.object({ ...base, kind: z.enum(['pattern.noise', 'pattern.stripes', 'pattern.checker']), coordinate: reference }).strict(),
]);

const rawShaderGraphSchema = z.object({
  version: z.literal(1),
  name: z.string().trim().min(1).max(80),
  description: z.string().trim().min(1).max(500),
  nodes: z.array(shaderNodeSchema).min(1).max(64),
  outputs: z.object({
    color: reference.optional(),
    roughness: reference.optional(),
    emissive: reference.optional(),
    opacity: reference.optional(),
  }).strict().refine((outputs) => Object.keys(outputs).length > 0, '材质图至少需要一个输出。'),
}).strict();

export type ShaderNode = z.infer<typeof shaderNodeSchema>;
export type ShaderGraph = z.infer<typeof rawShaderGraphSchema>;
export type ShaderValueType = 'float' | 'vec2' | 'vec3';
export type ShaderParameter = Extract<ShaderNode, { kind: 'parameter.float' | 'parameter.color' }>;
export type ShaderParameterValue = number | string;

export function shaderNodeReferences(node: ShaderNode): string[] {
  switch (node.kind) {
    case 'vector.component': return [node.input];
    case 'vector.rotate2d': return [node.input, node.angle];
    case 'math.add':
    case 'math.subtract':
    case 'math.multiply':
    case 'math.divide':
    case 'math.dot':
    case 'math.mod': return [node.a, node.b];
    case 'math.sin':
    case 'math.abs':
    case 'math.fract':
    case 'math.floor':
    case 'math.oneMinus': return [node.input];
    case 'math.pow': return [node.base, node.exponent];
    case 'math.mix': return [node.a, node.b, node.factor];
    case 'math.smoothstep': return [node.edge0, node.edge1, node.input];
    case 'math.clamp': return [node.input, node.min, node.max];
    case 'pattern.noise':
    case 'pattern.stripes':
    case 'pattern.checker': return [node.coordinate];
    default: return [];
  }
}

function isVector(type: ShaderValueType) {
  return type === 'vec2' || type === 'vec3';
}

export function validateShaderGraph(graph: ShaderGraph) {
  const byId = new Map<string, ShaderNode>();
  const parameterKeys = new Set<string>();
  for (const node of graph.nodes) {
    if (byId.has(node.id)) throw new Error(`材质图节点 ID 重复：${node.id}`);
    byId.set(node.id, node);
    if (node.kind === 'parameter.float' || node.kind === 'parameter.color') {
      if (parameterKeys.has(node.key)) throw new Error(`材质图参数键重复：${node.key}`);
      parameterKeys.add(node.key);
    }
  }

  const visiting = new Set<string>();
  const resolved = new Map<string, { type: ShaderValueType; depth: number }>();
  function resolve(id: string): { type: ShaderValueType; depth: number } {
    const cached = resolved.get(id);
    if (cached) return cached;
    const node = byId.get(id);
    if (!node) throw new Error(`材质图引用不存在：${id}`);
    if (visiting.has(id)) throw new Error(`材质图存在循环：${id}`);
    visiting.add(id);
    const dependencies = shaderNodeReferences(node).map(resolve);
    const depth = dependencies.length ? Math.max(...dependencies.map((value) => value.depth)) + 1 : 1;
    if (depth > 24) throw new Error('材质图连接深度超过 24。');
    const types = dependencies.map((value) => value.type);
    let type: ShaderValueType;
    switch (node.kind) {
      case 'input.uv': type = 'vec2'; break;
      case 'input.positionLocal':
      case 'input.normalView':
      case 'input.viewDirection':
      case 'input.materialColor':
      case 'input.materialEmissive':
      case 'value.color':
      case 'parameter.color': type = 'vec3'; break;
      case 'input.time':
      case 'input.materialRoughness':
      case 'input.materialOpacity':
      case 'value.float':
      case 'parameter.float': type = 'float'; break;
      case 'vector.component':
        if (!isVector(types[0]) || (types[0] === 'vec2' && node.component === 'z')) throw new Error(`${node.id} 的分量输入类型无效。`);
        type = 'float'; break;
      case 'vector.rotate2d':
        if (types[0] !== 'vec2' || types[1] !== 'float') throw new Error(`${node.id} 需要 vec2 坐标和 float 角度。`);
        type = 'vec2'; break;
      case 'math.add':
      case 'math.subtract':
        if (types[0] !== types[1]) throw new Error(`${node.id} 的两个输入类型必须一致。`);
        type = types[0]; break;
      case 'math.multiply':
        if (types[0] === types[1]) type = types[0];
        else if (types[0] === 'float' && isVector(types[1])) type = types[1];
        else if (types[1] === 'float' && isVector(types[0])) type = types[0];
        else throw new Error(`${node.id} 的乘法输入类型不兼容。`);
        break;
      case 'math.divide':
        if (types[0] === types[1] || (isVector(types[0]) && types[1] === 'float')) type = types[0];
        else throw new Error(`${node.id} 的除法输入类型不兼容。`);
        break;
      case 'math.dot':
        if (!isVector(types[0]) || types[0] !== types[1]) throw new Error(`${node.id} 的点积输入必须是同型向量。`);
        type = 'float'; break;
      case 'math.mod':
        if (types[0] !== 'float' || types[1] !== 'float') throw new Error(`${node.id} 的取模输入必须是 float。`);
        type = 'float'; break;
      case 'math.sin':
      case 'math.abs':
      case 'math.fract':
      case 'math.floor':
      case 'math.oneMinus':
        if (types[0] !== 'float') throw new Error(`${node.id} 的输入必须是 float。`);
        type = 'float'; break;
      case 'math.pow':
        if (types[0] !== 'float' || types[1] !== 'float') throw new Error(`${node.id} 的幂输入必须是 float。`);
        type = 'float'; break;
      case 'math.mix':
        if (types[0] !== types[1] || types[2] !== 'float') throw new Error(`${node.id} 的混合输入类型无效。`);
        type = types[0]; break;
      case 'math.smoothstep':
        if (types.some((value) => value !== 'float')) throw new Error(`${node.id} 的平滑阈值输入必须是 float。`);
        type = 'float'; break;
      case 'math.clamp':
        if (types.some((value) => value !== 'float')) throw new Error(`${node.id} 的限制输入必须是 float。`);
        type = 'float'; break;
      case 'pattern.noise':
      case 'pattern.stripes':
      case 'pattern.checker':
        if (!isVector(types[0])) throw new Error(`${node.id} 的图案坐标必须是向量。`);
        type = 'float'; break;
    }
    visiting.delete(id);
    const result = { type, depth };
    resolved.set(id, result);
    return result;
  }

  const expected: Record<keyof ShaderGraph['outputs'], ShaderValueType> = {
    color: 'vec3', roughness: 'float', emissive: 'vec3', opacity: 'float',
  };
  const reachable = new Set<string>();
  function mark(id: string) {
    if (reachable.has(id)) return;
    const node = byId.get(id);
    if (!node) throw new Error(`材质图输出引用不存在：${id}`);
    reachable.add(id);
    shaderNodeReferences(node).forEach(mark);
  }
  for (const [output, id] of Object.entries(graph.outputs) as Array<[keyof ShaderGraph['outputs'], string]>) {
    const actual = resolve(id).type;
    if (actual !== expected[output]) throw new Error(`${output} 输出需要 ${expected[output]}，实际为 ${actual}。`);
    mark(id);
  }
  if (reachable.size !== graph.nodes.length) throw new Error('材质图包含没有连接到输出的节点。');
  const edgeCount = graph.nodes.reduce((sum, node) => sum + shaderNodeReferences(node).length, 0);
  if (edgeCount > 160) throw new Error('材质图连接数量超过 160。');
  return graph;
}

export const shaderGraphSchema = rawShaderGraphSchema.superRefine((graph, context) => {
  try { validateShaderGraph(graph); }
  catch (error) { context.addIssue({ code: 'custom', message: error instanceof Error ? error.message : String(error) }); }
});

export function parseShaderGraph(input: unknown): ShaderGraph {
  return shaderGraphSchema.parse(input);
}

export function graphParameters(graph: ShaderGraph): ShaderParameter[] {
  return graph.nodes.filter((node): node is ShaderParameter => node.kind === 'parameter.float' || node.kind === 'parameter.color');
}

export function patchShaderGraphParameters(graph: ShaderGraph | null, values: Record<string, ShaderParameterValue>) {
  if (!graph) throw new Error('当前材质没有可修改的 Shader 图。');
  if (Object.keys(values).length === 0) throw new Error('Shader 参数修改不能为空。');
  const next = structuredClone(graph);
  const parameters = new Map(graphParameters(next).map((node) => [node.key, node]));
  for (const [key, value] of Object.entries(values)) {
    const parameter = parameters.get(key);
    if (!parameter) throw new Error(`Shader 参数不存在：${key}`);
    if (parameter.kind === 'parameter.float') {
      if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`${key} 需要数值。`);
      if (value < parameter.min || value > parameter.max) throw new Error(`${key} 必须位于 ${parameter.min}–${parameter.max}。`);
      parameter.value = value;
    } else {
      if (typeof value !== 'string' || !/^#[0-9a-fA-F]{6}$/.test(value)) throw new Error(`${key} 需要 #RRGGBB 颜色。`);
      parameter.value = value;
    }
  }
  return parseShaderGraph(next);
}

export function shaderGraphNeedsUv(graph: ShaderGraph) {
  return graph.nodes.some((node) => node.kind === 'input.uv');
}

export function shaderGraphUsesTime(graph: ShaderGraph) {
  return graph.nodes.some((node) => node.kind === 'input.time');
}

const wireKinds: Record<ShaderNode['kind'], string> = {
  'input.uv': 'i.uv',
  'input.positionLocal': 'i.position',
  'input.normalView': 'i.normal',
  'input.viewDirection': 'i.view',
  'input.time': 'i.time',
  'input.materialColor': 'i.materialColor',
  'input.materialRoughness': 'i.materialRoughness',
  'input.materialEmissive': 'i.materialEmissive',
  'input.materialOpacity': 'i.materialOpacity',
  'value.float': 'v.float',
  'value.color': 'v.color',
  'parameter.float': 'p.float',
  'parameter.color': 'p.color',
  'vector.component': 'v.component',
  'vector.rotate2d': 'v.rotate2d',
  'math.add': 'm.add',
  'math.subtract': 'm.subtract',
  'math.multiply': 'm.multiply',
  'math.divide': 'm.divide',
  'math.dot': 'm.dot',
  'math.mod': 'm.mod',
  'math.sin': 'm.sin',
  'math.abs': 'm.abs',
  'math.fract': 'm.fract',
  'math.floor': 'm.floor',
  'math.oneMinus': 'm.oneMinus',
  'math.pow': 'm.pow',
  'math.mix': 'm.mix',
  'math.smoothstep': 'm.smoothstep',
  'math.clamp': 'm.clamp',
  'pattern.noise': 'p.noise',
  'pattern.stripes': 'p.stripes',
  'pattern.checker': 'p.checker',
};

function encodeWireNode(node: ShaderNode): unknown[] {
  const head = [node.id, wireKinds[node.kind]];
  switch (node.kind) {
    case 'value.float':
    case 'value.color': return [...head, node.value];
    case 'parameter.float': return [...head, node.key, node.label, node.value, node.min, node.max];
    case 'parameter.color': return [...head, node.key, node.label, node.value];
    case 'vector.component': return [...head, node.input, node.component];
    case 'vector.rotate2d': return [...head, node.input, node.angle];
    case 'math.add':
    case 'math.subtract':
    case 'math.multiply':
    case 'math.divide':
    case 'math.dot':
    case 'math.mod': return [...head, node.a, node.b];
    case 'math.sin':
    case 'math.abs':
    case 'math.fract':
    case 'math.floor':
    case 'math.oneMinus': return [...head, node.input];
    case 'math.pow': return [...head, node.base, node.exponent];
    case 'math.mix': return [...head, node.a, node.b, node.factor];
    case 'math.smoothstep': return [...head, node.edge0, node.edge1, node.input];
    case 'math.clamp': return [...head, node.input, node.min, node.max];
    case 'pattern.noise':
    case 'pattern.stripes':
    case 'pattern.checker': return [...head, node.coordinate];
    default: return head;
  }
}

export function encodeShaderGraphWire(graph: ShaderGraph) {
  const parsed = parseShaderGraph(graph);
  return { ...parsed, nodes: parsed.nodes.map(encodeWireNode) };
}

function decodeWireNode(input: unknown): unknown {
  if (!Array.isArray(input)) return input;
  const [id, kind, a, b, c, d, e] = input;
  switch (kind) {
    case 'i.uv': return { id, kind: 'input.uv' };
    case 'i.position': return { id, kind: 'input.positionLocal' };
    case 'i.normal': return { id, kind: 'input.normalView' };
    case 'i.view': return { id, kind: 'input.viewDirection' };
    case 'i.time': return { id, kind: 'input.time' };
    case 'i.materialColor': return { id, kind: 'input.materialColor' };
    case 'i.materialRoughness': return { id, kind: 'input.materialRoughness' };
    case 'i.materialEmissive': return { id, kind: 'input.materialEmissive' };
    case 'i.materialOpacity': return { id, kind: 'input.materialOpacity' };
    case 'v.float': return { id, kind: 'value.float', value: a };
    case 'v.color': return { id, kind: 'value.color', value: a };
    case 'p.float': return { id, kind: 'parameter.float', key: a, label: b, value: c, min: d, max: e };
    case 'p.color': return { id, kind: 'parameter.color', key: a, label: b, value: c };
    case 'v.component': return { id, kind: 'vector.component', input: a, component: b };
    case 'v.rotate2d': return { id, kind: 'vector.rotate2d', input: a, angle: b };
    case 'm.add': return { id, kind: 'math.add', a, b };
    case 'm.subtract': return { id, kind: 'math.subtract', a, b };
    case 'm.multiply': return { id, kind: 'math.multiply', a, b };
    case 'm.divide': return { id, kind: 'math.divide', a, b };
    case 'm.dot': return { id, kind: 'math.dot', a, b };
    case 'm.mod': return { id, kind: 'math.mod', a, b };
    case 'm.sin': return { id, kind: 'math.sin', input: a };
    case 'm.abs': return { id, kind: 'math.abs', input: a };
    case 'm.fract': return { id, kind: 'math.fract', input: a };
    case 'm.floor': return { id, kind: 'math.floor', input: a };
    case 'm.oneMinus': return { id, kind: 'math.oneMinus', input: a };
    case 'm.pow': return { id, kind: 'math.pow', base: a, exponent: b };
    case 'm.mix': return { id, kind: 'math.mix', a, b, factor: c };
    case 'm.smoothstep': return { id, kind: 'math.smoothstep', edge0: a, edge1: b, input: c };
    case 'm.clamp': return { id, kind: 'math.clamp', input: a, min: b, max: c };
    case 'p.noise': return { id, kind: 'pattern.noise', coordinate: a };
    case 'p.stripes': return { id, kind: 'pattern.stripes', coordinate: a };
    case 'p.checker': return { id, kind: 'pattern.checker', coordinate: a };
    default: throw new Error(`不支持的紧凑 Shader 节点类型：${String(kind)}`);
  }
}

export function parseShaderGraphWire(input: unknown): ShaderGraph {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return parseShaderGraph(input);
  const record = input as Record<string, unknown>;
  if (!Array.isArray(record.nodes)) return parseShaderGraph(input);
  return parseShaderGraph({ ...record, nodes: record.nodes.map(decodeWireNode) });
}

export function createHologramGraph(): ShaderGraph {
  return parseShaderGraph({
    version: 1,
    name: '蓝色全息扫描',
    description: '局部位置和时间生成向上移动的扫描线，视线与法线生成明亮轮廓。',
    nodes: [
      { id: 'position', kind: 'input.positionLocal' },
      { id: 'height', kind: 'vector.component', input: 'position', component: 'y' },
      { id: 'scanDensity', kind: 'parameter.float', key: 'scanDensity', label: '扫描线密度', value: 18, min: 1, max: 80 },
      { id: 'heightScaled', kind: 'math.multiply', a: 'height', b: 'scanDensity' },
      { id: 'clock', kind: 'input.time' },
      { id: 'scanSpeed', kind: 'parameter.float', key: 'scanSpeed', label: '扫描速度', value: 0.8, min: -4, max: 4 },
      { id: 'timeOffset', kind: 'math.multiply', a: 'clock', b: 'scanSpeed' },
      { id: 'movingHeight', kind: 'math.subtract', a: 'heightScaled', b: 'timeOffset' },
      { id: 'phase', kind: 'math.fract', input: 'movingHeight' },
      { id: 'zero', kind: 'value.float', value: 0 },
      { id: 'scanWidth', kind: 'parameter.float', key: 'scanWidth', label: '扫描线宽度', value: 0.1, min: 0.01, max: 0.45 },
      { id: 'scanFade', kind: 'math.smoothstep', edge0: 'zero', edge1: 'scanWidth', input: 'phase' },
      { id: 'scanMask', kind: 'math.oneMinus', input: 'scanFade' },
      { id: 'normal', kind: 'input.normalView' },
      { id: 'view', kind: 'input.viewDirection' },
      { id: 'facingSigned', kind: 'math.dot', a: 'normal', b: 'view' },
      { id: 'facing', kind: 'math.abs', input: 'facingSigned' },
      { id: 'rimBase', kind: 'math.oneMinus', input: 'facing' },
      { id: 'rimPower', kind: 'parameter.float', key: 'rimPower', label: '轮廓范围', value: 2.4, min: 0.25, max: 8 },
      { id: 'rimMask', kind: 'math.pow', base: 'rimBase', exponent: 'rimPower' },
      { id: 'surfaceColor', kind: 'parameter.color', key: 'surfaceColor', label: '表面颜色', value: '#126BBD' },
      { id: 'scanColor', kind: 'parameter.color', key: 'scanColor', label: '扫描线颜色', value: '#35E6FF' },
      { id: 'rimColor', kind: 'parameter.color', key: 'rimColor', label: '轮廓颜色', value: '#79F7FF' },
      { id: 'scanGlow', kind: 'math.multiply', a: 'scanColor', b: 'scanMask' },
      { id: 'rimGlow', kind: 'math.multiply', a: 'rimColor', b: 'rimMask' },
      { id: 'emission', kind: 'math.add', a: 'scanGlow', b: 'rimGlow' },
      { id: 'baseOpacity', kind: 'parameter.float', key: 'baseOpacity', label: '基础不透明度', value: 0.28, min: 0.02, max: 1 },
      { id: 'scanOpacity', kind: 'parameter.float', key: 'scanOpacity', label: '扫描线不透明度', value: 0.3, min: 0, max: 1 },
      { id: 'scanAlpha', kind: 'math.multiply', a: 'scanMask', b: 'scanOpacity' },
      { id: 'rimOpacity', kind: 'parameter.float', key: 'rimOpacity', label: '轮廓不透明度', value: 0.5, min: 0, max: 1 },
      { id: 'rimAlpha', kind: 'math.multiply', a: 'rimMask', b: 'rimOpacity' },
      { id: 'alphaBaseScan', kind: 'math.add', a: 'baseOpacity', b: 'scanAlpha' },
      { id: 'alphaCombined', kind: 'math.add', a: 'alphaBaseScan', b: 'rimAlpha' },
      { id: 'one', kind: 'value.float', value: 1 },
      { id: 'opacity', kind: 'math.clamp', input: 'alphaCombined', min: 'zero', max: 'one' },
      { id: 'surfaceRoughness', kind: 'parameter.float', key: 'surfaceRoughness', label: '表面粗糙度', value: 0.28, min: 0.02, max: 1 },
    ],
    outputs: { color: 'surfaceColor', roughness: 'surfaceRoughness', emissive: 'emission', opacity: 'opacity' },
  });
}
