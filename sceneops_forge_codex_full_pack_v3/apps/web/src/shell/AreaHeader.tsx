import React from 'react';
import type { AreaHeaderContract } from '@sceneops/forge-shell';

type AreaAction = AreaHeaderContract['actions'][number];
export interface AreaHeaderProps {
  contract: AreaHeaderContract;
  onAction(action: AreaAction): void;
}

export function AreaHeader({ contract, onAction }: AreaHeaderProps): React.ReactElement {
  const quickActions: AreaAction[] = contract.compact ? ['close'] : ['add', 'maximize-restore', 'close'];
  const menuActions = contract.actions.filter(action => action !== 'editor-menu' && action !== 'more' && action !== 'close');
  return <header className={`forge-area-header${contract.active ? ' is-active' : ''}${contract.compact ? ' is-compact' : ''}`}>
    <button className="forge-editor-select" type="button" aria-label="选择功能" title={`选择功能 · 当前为${contract.title}`}
      onClick={() => onAction('editor-menu')}>
      <ActionIcon action="editor-menu"/><strong>{contract.title}</strong><span className="forge-select-chevron" aria-hidden="true">⌄</span>
    </button>
    {!contract.compact && <span className="forge-area-context" title={contract.contextSummary}>{contract.contextSummary}</span>}
    {contract.mode !== 'live' && <span className="forge-area-mode" title="界面执行模式">{MODE_LABELS[contract.mode]}</span>}
    <nav aria-label="区域操作">
      {quickActions.filter(action => action !== 'close' && contract.actions.includes(action)).map(action =>
        <button className="forge-icon-button" key={action} type="button" aria-label={ACTION_LABELS[action]} title={ACTION_LABELS[action]} onClick={() => onAction(action)}><ActionIcon action={action}/></button>)}
      {contract.actions.includes('more') && <details className="forge-area-more" onKeyDown={event => { if (event.key === 'Escape') { event.currentTarget.open = false; event.stopPropagation(); } }}>
        <summary aria-label="更多区域操作" title="更多区域操作"><ActionIcon action="more"/></summary>
        <div className="forge-area-menu">
          <p>区域操作</p>
          {menuActions.map(action => <button key={action} type="button" onClick={event => { event.currentTarget.closest('details')?.removeAttribute('open'); onAction(action); }}><ActionIcon action={action}/>{ACTION_LABELS[action]}</button>)}
        </div>
      </details>}
      {contract.actions.includes('close') && <button className="forge-icon-button" type="button" aria-label="关闭" title="关闭当前区域" onClick={() => onAction('close')}><ActionIcon action="close"/></button>}
    </nav>
  </header>;
}

function ActionIcon({ action }: { action: AreaAction }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    {action === 'editor-menu' && <><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></>}
    {action === 'add' && <path d="M12 5v14M5 12h14"/>}
    {action === 'close' && <path d="m6 6 12 12M18 6 6 18"/>}
    {action === 'split' && <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/></>}
    {action === 'float' && <><path d="M9 6H5a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-4"/><path d="M13 3h8v8M21 3 10 14"/></>}
    {action === 'maximize-restore' && <path d="M9 4H4v5m11-5h5v5M4 15v5h5m11-5v5h-5"/>}
    {action === 'follow-pin' && <><path d="m8 3 8 0-1 7 3 3v2H6v-2l3-3-1-7ZM12 15v6"/></>}
    {action === 'more' && <><circle cx="5" cy="12" r="1" fill="currentColor"/><circle cx="12" cy="12" r="1" fill="currentColor"/><circle cx="19" cy="12" r="1" fill="currentColor"/></>}
  </svg>;
}
const MODE_LABELS = { live: '本地', mock: '模拟', cached: '缓存', planned: '计划', blocked: '受阻' };
const ACTION_LABELS: Record<AreaAction, string> = {
  'editor-menu': '选择功能', 'follow-pin': '跟随 / 固定上下文', add: '添加标签',
  split: '拆分区域', float: '浮动窗口', 'maximize-restore': '最大化 / 恢复',
  more: '更多区域操作', close: '关闭',
};
