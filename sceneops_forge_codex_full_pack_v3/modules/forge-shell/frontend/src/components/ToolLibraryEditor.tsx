import { useId, useMemo, useState } from 'react';
import type { EditorHostProps, EditorPlacement } from '../contracts.ts';
import { useShellTools } from './ToolRuntime.ts';
import { createToolLibraryTree } from './tool-library-tree.ts';
import './tool-picker.css';

type PlacementChoice = 'current' | 'right' | 'left' | 'above' | 'below' | 'tab' | 'floating' | 'popout';

export default function ToolLibraryEditor({ instanceId, context }: EditorHostProps) {
  const runtime = useShellTools();
  const [query, setQuery] = useState('');
  const [placement, setPlacement] = useState<PlacementChoice>('current');
  const [error, setError] = useState('');
  const searchId = useId();
  const placements: Record<PlacementChoice, EditorPlacement> = {
    current: { mode: 'replace', relativeToInstanceId: instanceId },
    right: { mode: 'split', direction: 'right', relativeToInstanceId: instanceId }, left: { mode: 'split', direction: 'left', relativeToInstanceId: instanceId },
    above: { mode: 'split', direction: 'above', relativeToInstanceId: instanceId }, below: { mode: 'split', direction: 'below', relativeToInstanceId: instanceId },
    tab: { mode: 'tab', relativeToInstanceId: instanceId }, floating: { mode: 'floating' }, popout: { mode: 'popout' },
  };
  const branches = useMemo(
    () => createToolLibraryTree(runtime.editors, query, runtime.toolLibraryCatalog),
    [query, runtime.editors, runtime.toolLibraryCatalog],
  );
  return <section className="shell-tool-content picker-tool-library" aria-label="工具库">
    {!runtime.toolLibraryCatalog && runtime.renderTaskActivity?.(context.projectId)}
    <div className="picker-toolbar">
      <div className="picker-search-control"><svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="10.8" cy="10.8" r="5.8" /><path d="m16 16 4 4" /></svg><input id={searchId} aria-label="搜索工具" placeholder="搜索功能或用途" value={query} onChange={e => setQuery(e.target.value)} /></div>
      <select aria-label="打开位置" title="默认替换当前区域，保留位置和尺寸" value={placement} onChange={e => setPlacement(e.target.value as PlacementChoice)}>
      {Object.entries({ current: '当前区域', tab: '当前区域新标签', right: '右侧拆分', left: '左侧拆分', above: '上方拆分', below: '下方拆分', floating: '浮动', popout: '弹出窗口' }).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
      </select>
    </div>
    <div className="picker-options" aria-label="可选功能">
      <div className="picker-tool-tree">{branches.map(branch => <section className={`picker-tree-branch is-${branch.kind}`} key={branch.id} aria-labelledby={`${searchId}-${branch.id}`}>
        <header className="picker-tree-branch-header">
          <span className="picker-tree-junction" aria-hidden="true" />
          <span><strong id={`${searchId}-${branch.id}`}>{branch.title}</strong><small>{branch.description}</small></span>
        </header>
        <ol className="picker-tree-nodes">{branch.nodes.map(node => <li key={node.id}>
          <span className="picker-tree-step" aria-hidden="true">{node.sequence ?? '·'}</span>
          <button className="picker-tree-node" title={`${node.title} · ${node.description}\n${node.editor.id}`} onClick={() => void (placement === 'current'
            ? runtime.execute('workbench.switch_editor', { instanceId, editorId: node.editor.id })
            : runtime.open(node.editor.id, placements[placement])).catch(e => setError(e instanceof Error ? e.message : String(e)))}>
            <span className="picker-tree-node-copy"><strong>{node.title}</strong><small>{node.editor.title} · {node.description}</small></span>
            {node.editor.id.startsWith('workbench.') && runtime.renderProductionNodeStatus?.(context.projectId, node.editor.id.slice('workbench.'.length))}
            <svg className="picker-open-arrow" aria-hidden="true" viewBox="0 0 24 24"><path d="M5 12h13M13 6l6 6-6 6" /></svg>
          </button>
        </li>)}</ol>
      </section>)}</div>
    {!branches.length && <div className="picker-empty"><strong>没有找到匹配的功能</strong><span>尝试功能名称、用途或生产阶段关键词。</span></div>}
    </div>
    {error && <p className="picker-feedback is-error" role="alert"><span aria-hidden="true">!</span><span><strong>无法打开功能</strong>{error}</span></p>}
  </section>;
}
