import {
  abs, add, clamp, color, cos, div, dot, float, floor, fract, materialColor, materialEmissive, materialOpacity,
  materialRoughness, mix, mod, mul, mx_noise_float, normalView, positionLocal, positionViewDirection, pow,
  sin, smoothstep, sub, time, uv, vec2, vec3,
} from 'three/tsl';
import { parseShaderGraph, shaderGraphNeedsUv, type ShaderGraph, type ShaderNode, type ShaderValueType } from './shader-graph';

type DynamicNode = unknown;
type CompiledValue = { node: DynamicNode; type: ShaderValueType };
type FloatNode = ReturnType<typeof float>;
type VectorNode = ReturnType<typeof vec3>;
export type CompiledShaderGraph = { color?: VectorNode; roughness?: FloatNode; emissive?: VectorNode; opacity?: FloatNode };

// TSL's overloads encode static vector widths. The graph validator proves those widths first; this small adapter then
// invokes the same public TSL functions for a graph whose node types are known only at runtime.
const invoke = (fn: unknown, ...values: unknown[]) => (fn as (...input: unknown[]) => unknown)(...values);
const component = (node: DynamicNode, key: 'x' | 'y' | 'z') => (node as Record<'x' | 'y' | 'z', unknown>)[key];

export function compileShaderGraph(input: ShaderGraph, hasUv: boolean): CompiledShaderGraph {
  const graph = parseShaderGraph(input);
  if (shaderGraphNeedsUv(graph) && !hasUv) throw new Error('这个 Shader 图需要 UV；请先在建模软件中展开 UV。');
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const compiled = new Map<string, CompiledValue>();
  const active = new Set<string>();

  function build(id: string): CompiledValue {
    const cached = compiled.get(id);
    if (cached) return cached;
    const source = byId.get(id);
    if (!source) throw new Error(`Shader 节点不存在：${id}`);
    if (active.has(id)) throw new Error(`Shader 图存在循环：${id}`);
    active.add(id);
    const get = (reference: string) => build(reference).node;
    let value: CompiledValue;
    switch (source.kind) {
      case 'input.uv': value = { node: uv(), type: 'vec2' }; break;
      case 'input.positionLocal': value = { node: positionLocal, type: 'vec3' }; break;
      case 'input.normalView': value = { node: normalView, type: 'vec3' }; break;
      case 'input.viewDirection': value = { node: positionViewDirection, type: 'vec3' }; break;
      case 'input.time': value = { node: time, type: 'float' }; break;
      case 'input.materialColor': value = { node: materialColor.rgb, type: 'vec3' }; break;
      case 'input.materialRoughness': value = { node: materialRoughness, type: 'float' }; break;
      case 'input.materialEmissive': value = { node: materialEmissive, type: 'vec3' }; break;
      case 'input.materialOpacity': value = { node: materialOpacity, type: 'float' }; break;
      case 'value.float': value = { node: float(source.value), type: 'float' }; break;
      case 'value.color': value = { node: invoke(vec3, color(source.value)), type: 'vec3' }; break;
      case 'parameter.float': value = { node: float(source.value), type: 'float' }; break;
      case 'parameter.color': value = { node: invoke(vec3, color(source.value)), type: 'vec3' }; break;
      case 'vector.component': value = { node: component(get(source.input), source.component), type: 'float' }; break;
      case 'vector.rotate2d': {
        const coordinates = get(source.input);
        const angle = get(source.angle);
        const x = component(coordinates, 'x');
        const y = component(coordinates, 'y');
        value = {
          node: invoke(vec2,
            invoke(sub, invoke(mul, x, invoke(cos, angle)), invoke(mul, y, invoke(sin, angle))),
            invoke(add, invoke(mul, x, invoke(sin, angle)), invoke(mul, y, invoke(cos, angle))),
          ),
          type: 'vec2',
        };
        break;
      }
      case 'math.add': value = binary(source, add); break;
      case 'math.subtract': value = binary(source, sub); break;
      case 'math.multiply': value = binary(source, mul); break;
      case 'math.divide': value = binary(source, div); break;
      case 'math.dot': value = { node: invoke(dot, get(source.a), get(source.b)), type: 'float' }; break;
      case 'math.mod': value = { node: invoke(mod, get(source.a), get(source.b)), type: 'float' }; break;
      case 'math.sin': value = { node: invoke(sin, get(source.input)), type: 'float' }; break;
      case 'math.abs': value = { node: invoke(abs, get(source.input)), type: 'float' }; break;
      case 'math.fract': value = { node: invoke(fract, get(source.input)), type: 'float' }; break;
      case 'math.floor': value = { node: invoke(floor, get(source.input)), type: 'float' }; break;
      case 'math.oneMinus': value = { node: invoke(sub, 1, get(source.input)), type: 'float' }; break;
      case 'math.pow': value = { node: invoke(pow, get(source.base), get(source.exponent)), type: 'float' }; break;
      case 'math.mix': value = { node: invoke(mix, get(source.a), get(source.b), get(source.factor)), type: build(source.a).type }; break;
      case 'math.smoothstep': value = { node: invoke(smoothstep, get(source.edge0), get(source.edge1), get(source.input)), type: 'float' }; break;
      case 'math.clamp': value = { node: invoke(clamp, get(source.input), get(source.min), get(source.max)), type: 'float' }; break;
      case 'pattern.noise': value = { node: invoke(add, invoke(mul, invoke(mx_noise_float, get(source.coordinate)), 0.5), 0.5), type: 'float' }; break;
      case 'pattern.stripes': value = { node: invoke(add, invoke(mul, invoke(sin, invoke(mul, component(get(source.coordinate), 'x'), Math.PI * 2)), 0.5), 0.5), type: 'float' }; break;
      case 'pattern.checker': value = { node: invoke(mod, invoke(add, invoke(floor, component(get(source.coordinate), 'x')), invoke(floor, component(get(source.coordinate), 'y'))), 2), type: 'float' }; break;
    }
    active.delete(id);
    compiled.set(id, value);
    return value;
  }

  function binary(source: ShaderNode & { a: string; b: string }, operation: unknown): CompiledValue {
    const a = build(source.a);
    const b = build(source.b);
    return { node: invoke(operation, a.node, b.node), type: a.type === 'float' ? b.type : a.type };
  }

  return {
    ...(graph.outputs.color ? { color: build(graph.outputs.color).node as VectorNode } : {}),
    ...(graph.outputs.roughness ? { roughness: build(graph.outputs.roughness).node as FloatNode } : {}),
    ...(graph.outputs.emissive ? { emissive: build(graph.outputs.emissive).node as VectorNode } : {}),
    ...(graph.outputs.opacity ? { opacity: build(graph.outputs.opacity).node as FloatNode } : {}),
  };
}
