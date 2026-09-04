import { useState } from 'react';
import type { GameplayGraph, GameplayNode, GameplayEdge } from './api-types.ts';

export function NodeInspector({ graph, node, update, onSelectObject }: {
  graph: GameplayGraph; node: GameplayNode; update: (graph: GameplayGraph) => void;
  onSelectObject: (id: string) => void;
}) {
  const [jsonText, setJsonText] = useState(JSON.stringify({ conditions: node.conditions ?? [], effects: node.effects ?? [] }, null, 2));
  const [error, setError] = useState('');
  const patchNode = (patch: Partial<GameplayNode>) => update({ ...graph, nodes: graph.nodes.map(item => item.node_id === node.node_id ? { ...item, ...patch } : item) });
  const patchEdge = (edgeId: string, patch: Partial<GameplayEdge>) => update({ ...graph, edges: (graph.edges ?? []).map(edge => edge.edge_id === edgeId ? { ...edge, ...patch } : edge) });
  function applyConditions() {
    try {
      const value = JSON.parse(jsonText);
      if (!value || !Array.isArray(value.conditions) || !Array.isArray(value.effects) || Object.keys(value).some(key => !['conditions', 'effects'].includes(key))) throw new Error('只接受 conditions 与 effects 数组；语义由服务验证。');
      patchNode({ conditions: value.conditions, effects: value.effects }); setError('');
    } catch (cause) { setError(String(cause)); }
  }
  return <aside className="node-inspector"><h3>节点草稿</h3><code>{node.node_id}</code>
    <label>显示名称<input aria-label="节点显示名称" value={node.label} onChange={event => patchNode({ label: event.target.value })}/></label>
    <label>节点类型<select value={node.kind} onChange={event => patchNode({ kind: event.target.value as GameplayNode['kind'] })}>{['start','state','interaction','quest','dialogue','feedback','ending'].map(kind => <option key={kind}>{kind}</option>)}</select></label>
    <h4>绑定稳定对象 ID</h4>{(graph.scene_objects ?? []).map(object => <div className="binding-row" key={object.sceneops_id}><label><input type="checkbox" checked={(node.sceneops_ids ?? []).includes(object.sceneops_id)} onChange={event => patchNode({ sceneops_ids: event.target.checked ? [...(node.sceneops_ids ?? []), object.sceneops_id] : (node.sceneops_ids ?? []).filter(id => id !== object.sceneops_id) })}/>{object.display_name}</label><button title={object.sceneops_id} onClick={() => onSelectObject(object.sceneops_id)}>定位</button></div>)}
    <h4>出边 / 交互</h4>{(graph.edges ?? []).filter(edge => edge.source_node_id === node.node_id).map(edge => <div className="edge-editor" key={edge.edge_id}><code>{edge.edge_id}</code><select aria-label={`目标 ${edge.edge_id}`} value={edge.target_node_id} onChange={event => patchEdge(edge.edge_id, { target_node_id: event.target.value })}>{graph.nodes.map(target => <option key={target.node_id} value={target.node_id}>{target.label}</option>)}</select><select aria-label={`事件 ${edge.edge_id}`} value={edge.event_id ?? ''} onChange={event => patchEdge(edge.edge_id, { event_id: event.target.value || null })}><option value="">自动 / 无事件</option>{(graph.events ?? []).map(event => <option key={event.event_id}>{event.event_id}</option>)}</select><small>{edge.conditions?.length ?? 0} 条条件 · {edge.effects?.length ?? 0} 个效果</small><button onClick={() => update({ ...graph, edges: (graph.edges ?? []).filter(item => item.edge_id !== edge.edge_id) })}>删除这条边</button></div>)}
    <button onClick={() => update({ ...graph, edges: [...(graph.edges ?? []), { edge_id: `edge_${crypto.randomUUID()}`, source_node_id: node.node_id, target_node_id: graph.nodes.find(item => item.node_id !== node.node_id)?.node_id ?? node.node_id, conditions: [], effects: [], emitted_event_ids: [] }] })}>添加出边</button>
    <details><summary>编辑节点条件 / 效果 JSON</summary><textarea className="code-input" aria-label="条件与效果 JSON" value={jsonText} onChange={event => setJsonText(event.target.value)}/><button onClick={applyConditions}>更新节点草稿</button>{error && <p className="error" role="alert">{error}</p>}</details>
  </aside>;
}
