import React, { useState } from 'react';
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
  return <section className="shell-tool-content" aria-label="工具库">
    <h2>工具库 <small>LIVE · 本地停靠</small></h2>
    <input aria-label="搜索工具" placeholder="搜索已启用工具" value={query} onChange={e => setQuery(e.target.value)} />
    <select aria-label="打开位置" value={placement} onChange={e => setPlacement(e.target.value)}>
      {Object.entries({ right: '右侧拆分', left: '左侧拆分', above: '上方拆分', below: '下方拆分', tab: '标签', floating: '浮动', popout: '弹出窗口' }).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
    </select>
    {runtime.editors.filter(e => `${e.title} ${e.id}`.includes(query)).map(editor => <p key={editor.id}>
      <button onClick={() => void runtime.open(editor.id, placements[placement]).catch(e => setError(e.message))}>{editor.title}</button> <small>{editor.id}</small>
    </p>)}
    <p>拖动标签可重新停靠。右上角窗口菜单提供四边抽屉。其他业务工作台独立启动。</p>
    {error && <p role="alert">BLOCKED · {error}</p>}
  </section>;
}
