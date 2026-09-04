import React from 'react';
import type { AreaHeaderContract } from '@sceneops/forge-shell';

export interface AreaHeaderProps {
  contract: AreaHeaderContract;
  onAction(action: AreaHeaderContract['actions'][number]): void;
}

export function AreaHeader({ contract, onAction }: AreaHeaderProps): React.ReactElement {
  const visibleActions = contract.compact
    ? contract.actions.filter((action) => ['editor-menu', 'follow-pin', 'more', 'close'].includes(action))
    : contract.actions;
  return (
    <header className={contract.active ? 'forge-area-header is-active' : 'forge-area-header'}>
      <div className="forge-area-heading">
        <strong>{contract.title}</strong>
        <span>{contract.contextSummary}</span>
        <span aria-label={`执行模式 ${contract.mode}`}>{contract.mode.toUpperCase()}</span>
      </div>
      <nav aria-label="区域操作">
        {visibleActions.map((action) => (
          <button key={action} type="button" onClick={() => onAction(action)}>
            {ACTION_LABELS[action]}
          </button>
        ))}
      </nav>
    </header>
  );
}

const ACTION_LABELS: Record<AreaHeaderContract['actions'][number], string> = {
  'editor-menu': '编辑器',
  'follow-pin': '跟随/固定',
  add: '添加',
  split: '拆分',
  float: '浮动',
  'maximize-restore': '最大化/恢复',
  more: '更多',
  close: '关闭',
};
