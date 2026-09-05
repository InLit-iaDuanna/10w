import React, { useMemo, useState } from 'react';
import type { EditorPlacement } from '../contracts.ts';
import { useShellTools } from './ToolRuntime.ts';
export default function ToolLibraryEditor() {
  const runtime = useShellTools();
  const [query, setQuery] = useState('');
  const [placement, setPlacement] = useState('right');
  const [error, setError] = useState('');
  const placements: Record<string, EditorPlacement> = {
    right: { mode: 'split', direction: 'right' }, left: { mode: 'split', direction: 'left' },
    above: { mode: 'split', direction: 'above' }, below: { mode: 'split', direction: 'below' },
    tab: { mode: 'tab' }, floating: { mode: 'floating' }, popout: { mode: 'popout' },
  };
  const visibleEditors = useMemo(() => runtime.editors.filter(editor =>
    `${editor.title} ${editor.id} ${editor.category}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
  ), [query, runtime.editors]);
  const groupedEditors = useMemo(() => visibleEditors.reduce<Record<string, typeof visibleEditors>>((groups, editor) => {
    const group = editor.category || '其他工具';
    (groups[group] ??= []).push(editor);
    return groups;
  }, {}), [visibleEditors]);
  return <section className="shell-tool-content" aria-label="工具库">
    <header className="tool-library-header"><div><span className="tool-kicker">WORKBENCH LIBRARY</span><h2>工具库</h2><p>按需要拉入工具，不改变当前对话的焦点。</p></div><small>本地停靠</small></header>
    <div className="tool-library-controls"><label><span>查找工具</span><input aria-label="搜索工具" placeholder="名称、ID 或类别" value={query} onChange={e => setQuery(e.target.value)} /></label>
    <label><span>打开位置</span><select aria-label="打开位置" value={placement} onChange={e => setPlacement(e.target.value)}>
      {Object.entries({ right: '右侧拆分', left: '左侧拆分', above: '上方拆分', below: '下方拆分', tab: '标签', floating: '浮动', popout: '弹出窗口' }).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
    </select></label></div>
    <p className="tool-library-count">{visibleEditors.length} 个已注册工具 · 拖动标签可重新停靠</p>
    <div className="tool-library-groups">{Object.entries(groupedEditors).map(([group, editors]) => <section key={group} className="tool-library-group"><h3>{group}</h3>{editors.map(editor => <button className="tool-library-item" key={editor.id} onClick={() => void runtime.open(editor.id, placements[placement]).catch(e => setError(e.message))}>
      <span>{editor.title}<small>{editor.id}</small></span><b aria-hidden="true">＋</b>
    </button>)}</section>)}</div>
    {!visibleEditors.length && <div className="tool-library-empty"><strong>没有匹配的工具</strong><span>尝试搜索功能名称或清除关键词。</span></div>}
    {error && <p role="alert">BLOCKED · {error}</p>}
  </section>;
}
