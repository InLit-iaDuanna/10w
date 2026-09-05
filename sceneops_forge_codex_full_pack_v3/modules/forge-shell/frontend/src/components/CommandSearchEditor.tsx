import React, { useState } from 'react';
import type { EditorHostProps } from '../contracts.ts';
import { useShellTools } from './ToolRuntime.ts';
export default function CommandSearchEditor({ instanceId }: EditorHostProps) {
  const runtime = useShellTools();
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const actions = [
    ...runtime.editors.map(e => ({ title: `打开${e.title}`, run: () => runtime.execute('workbench.switch_editor', { instanceId, editorId: e.id }) })),
    { title: '撤销布局操作', run: () => runtime.execute('workspace.undo_layout', {}) },
    { title: '重新打开已关闭工具', run: () => runtime.execute('workbench.reopen_editor', {}) },
    { title: '保存当前布局', run: async () => { runtime.save(); } },
    { title: '重置为纯对话首页', run: () => runtime.execute('workspace.reset', { presetId: 'home' }) },
  ];
  const matches = actions.filter(action => action.title.includes(query));
  return <section className="shell-tool-content command-search" aria-label="命令搜索">
    <header><span className="tool-kicker">COMMAND CENTER</span><h2>命令搜索</h2><p>所有入口都通过同一工作台命令处理。</p></header>
    <label className="command-search-input"><span>搜索</span><input autoFocus aria-label="搜索命令" placeholder="搜索命令或工具" value={query} onChange={e => setQuery(e.target.value)} /></label>
    <div className="command-search-results">{matches.map((action, index) => <button key={action.title} onClick={() => void action.run().then(() => setStatus('已执行 · 当前工作台已更新')).catch(e => setStatus(`BLOCKED · ${e.message}`))}><kbd>{index + 1}</kbd>{action.title}<span aria-hidden="true">↵</span></button>)}</div>
    {!matches.length && <p className="tool-library-empty">没有匹配的命令。</p>}
    {status && <p role="status">{status}</p>}
  </section>;
}
