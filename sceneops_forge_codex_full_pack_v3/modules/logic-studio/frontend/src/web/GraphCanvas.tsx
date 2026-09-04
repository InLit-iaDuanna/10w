import type { GameplayGraph } from './api-types.ts';

export function GraphCanvas({ graph, selectedNode, selectedObject, currentNode, onSelect }: {
  graph: GameplayGraph; selectedNode: string; selectedObject: string | null;
  currentNode?: string; onSelect: (nodeId: string) => void;
}) {
  const columns = 3, width = 720, cellWidth = 236, cellHeight = 130;
  const position = new Map(graph.nodes.map((node, index) => [node.node_id, { x: 12 + index % columns * cellWidth, y: 18 + Math.floor(index / columns) * cellHeight }]));
  const height = Math.max(270, Math.ceil(graph.nodes.length / columns) * cellHeight + 10);
  return <div className="graph-canvas"><svg viewBox={`0 0 ${width} ${height}`} aria-label="玩法状态图" role="group">
    <defs><marker id="graph-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#6d858d"/></marker></defs>
    {(graph.edges ?? []).map(edge => {
      const source = position.get(edge.source_node_id), target = position.get(edge.target_node_id);
      if (!source || !target) return null;
      const startX = source.x + 105, startY = source.y + 83, endX = target.x + 105, endY = target.y;
      return <g key={edge.edge_id}><path d={`M${startX},${startY} C${startX},${startY + 30} ${endX},${endY - 25} ${endX},${endY}`} fill="none" stroke="#536b73" strokeWidth="1.5" markerEnd="url(#graph-arrow)"/><title>{edge.edge_id}{edge.conditions?.length ? ' · 有条件' : ''}</title></g>;
    })}
    {graph.nodes.map(node => {
      const p = position.get(node.node_id)!;
      const linked = !!selectedObject && (node.sceneops_ids ?? []).includes(selectedObject);
      return <g key={node.node_id} transform={`translate(${p.x},${p.y})`} role="button" tabIndex={0} aria-label={`节点 ${node.label}`} aria-pressed={selectedNode === node.node_id} onClick={() => onSelect(node.node_id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(node.node_id); } }} className={`graph-node ${selectedNode === node.node_id ? 'active' : ''} ${linked ? 'linked' : ''}`}>
        <rect width="210" height="82" rx="5"/>{currentNode === node.node_id && <circle cx="193" cy="17" r="5" fill="#55c98b"/>}
        <text x="12" y="20" className="node-kind">{node.kind} {linked ? '· 关联所选对象' : ''}</text><text x="12" y="43" className="node-title">{node.label.slice(0, 24)}</text><text x="12" y="66" className="node-id">{node.node_id.slice(0, 30)}</text>
      </g>;
    })}
  </svg></div>;
}
