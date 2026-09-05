import React, { useId, useState } from 'react';
import type { EditorHostProps } from '../contracts.ts';
import { useShellTools } from './ToolRuntime.ts';
import './tool-picker.css';

export default function CommandSearchEditor({ instanceId }: EditorHostProps) {
  const runtime = useShellTools();
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const searchId = useId();
  const actions = [
    ...runtime.editors.map(e => ({ title: `打开${e.title}`, description: '在当前区域打开功能', run: () => runtime.execute('workbench.switch_editor', { instanceId, editorId: e.id }) })),
    { title: '撤销布局操作', description: '工作台操作', run: () => runtime.execute('workspace.undo_layout', {}) },
    { title: '重新打开已关闭工具', description: '工作台操作', run: () => runtime.execute('workbench.reopen_editor', {}) },
    { title: '保存当前布局', description: '工作台操作', run: async () => { runtime.save(); } },
    { title: '重置为纯对话首页', description: '工作台操作', run: () => runtime.execute('workspace.reset', { presetId: 'home' }) },
  ];
  const matches = actions.filter(action => action.title.includes(query));
  return <section className="shell-tool-content picker-command-search" aria-label="命令搜索">
    <header className="picker-header">
      <div><span className="picker-eyebrow">WORKBENCH / COMMANDS</span><h2>命令搜索</h2><p>用同一套工作台命令打开功能、调整布局或恢复工作。</p></div>
      <span className="picker-mode"><span aria-hidden="true">↵</span> 执行命令</span>
    </header>
    <div className="picker-search-field picker-command-input">
      <label htmlFor={searchId}>快速查找</label>
      <div className="picker-search-control"><svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="10.8" cy="10.8" r="5.8" /><path d="m16 16 4 4" /></svg><input id={searchId} autoFocus aria-label="搜索命令" placeholder="搜索命令或工具" value={query} onChange={e => setQuery(e.target.value)} /></div>
    </div>
    <div className="picker-list-meta"><span>{matches.length} 条匹配命令</span><span>选择一条命令</span></div>
    <div className="picker-command-results">{matches.map((action, index) => <button key={action.title} onClick={() => void action.run().then(() => setStatus('已执行 · 当前工作台已更新')).catch(e => setStatus(`BLOCKED · ${e.message}`))}><kbd>{index + 1}</kbd><span>{action.title}<small>{action.description}</small></span><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M5 12h13M13 6l6 6-6 6" /></svg></button>)}</div>
    {!matches.length && <div className="picker-empty"><strong>没有匹配的命令</strong><span>换一个功能名称或工作台操作试试。</span></div>}
    {status && <p className={`picker-feedback ${status.startsWith('BLOCKED') ? 'is-error' : 'is-success'}`} role="status"><span aria-hidden="true">{status.startsWith('BLOCKED') ? '!' : '✓'}</span><span>{status}</span></p>}
  </section>;
}
