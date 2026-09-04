import React, { useState } from 'react';
import { useShellTools } from './ToolRuntime.ts';
export default function CommandSearchEditor() {
  const runtime = useShellTools();
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const actions = [
    ...runtime.editors.map(e => ({ title: `打开${e.title}`, run: () => runtime.open(e.id, { mode: 'split', direction: 'right' }) })),
    { title: '撤销布局操作', run: () => runtime.execute('workspace.undo_layout', {}) },
    { title: '重新打开已关闭工具', run: () => runtime.execute('workbench.reopen_editor', {}) },
    { title: '保存当前布局', run: async () => { runtime.save(); } },
    { title: '重置为纯对话首页', run: () => runtime.execute('workspace.reset', { presetId: 'home' }) },
  ];
  return <section className="shell-tool-content" aria-label="命令搜索">
    <h2>命令搜索</h2><input autoFocus aria-label="搜索命令" placeholder="搜索命令或工具" value={query} onChange={e => setQuery(e.target.value)} />
    {actions.filter(a => a.title.includes(query)).map(a => <p key={a.title}><button onClick={() => void a.run().then(() => setStatus('LIVE · 已执行')).catch(e => setStatus(`BLOCKED · ${e.message}`))}>{a.title}</button></p>)}
    <p role="status">{status}</p>
  </section>;
}
