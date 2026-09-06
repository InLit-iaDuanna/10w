import type { JourneyChange } from './journey-client';
import { MarkdownMessage } from '../../../../packages/core-ui/frontend/src/index.ts';

export function JourneyChangeReview({ change, disabled, onResolve }: {
  change: JourneyChange; disabled: boolean; onResolve: (accept: boolean) => void;
}) {
  const before = change.before_cards ?? [], after = change.after_cards ?? [];
  const ids = [...new Set([...before.map(card => card.id), ...after.map(card => card.id)])];
  const labels = { title: '标题', experience: '目标体验', core_loop: '核心循环', scope: '范围', acceptance: '验收条件', assumptions: '假设' };
  return <section className="journey-change" aria-label="待确认修改提案">
    <header><strong>修改提案</strong><small>确认后更新草稿，不自动提交正式版本</small></header>
    <MarkdownMessage text={change.rationale || '根据你的反馈调整策划。'} />
    <details open><summary>查看前后变化</summary>
      {(Object.keys(labels) as (keyof typeof labels)[]).map(field => {
        const old = change.before_outline?.[field], next = change.after_outline?.[field];
        if (JSON.stringify(old) === JSON.stringify(next)) return null;
        return <div className="journey-field-diff" key={field}><strong>{labels[field]}</strong>
          <div><small>原内容</small><MarkdownMessage text={Array.isArray(old) ? old.join('\n') : old || '无'} /></div>
          <div><small>建议改为</small><MarkdownMessage text={Array.isArray(next) ? next.join('\n') : next || '无'} /></div></div>;
      })}
      {ids.map(id => {
        const old = before.find(card => card.id === id), next = after.find(card => card.id === id);
        if (JSON.stringify(old) === JSON.stringify(next)) return null;
        return <div className="journey-field-diff" key={id}><strong>{!old ? '新增' : !next ? '移除' : '修改'}卡片 · {next?.title ?? old?.title}</strong>
          {old && <div><small>原内容</small><MarkdownMessage text={`${old.title}\n\n${old.description}\n\n完成条件：${old.acceptance}\n\n依赖：${old.dependencies?.join('、') || '无'}`} /></div>}
          {next && <div><small>建议改为</small><MarkdownMessage text={`${next.title}\n\n${next.description}\n\n完成条件：${next.acceptance}\n\n依赖：${next.dependencies?.join('、') || '无'}`} /></div>}
          {!next && <small>已有 Git 分支和文件保留，不会被删除。</small>}</div>;
      })}
    </details>
    <footer><button type="button" disabled={disabled} onClick={() => onResolve(false)}>不采用</button><button type="button" disabled={disabled} onClick={() => onResolve(true)}>确认采用修改</button></footer>
  </section>;
}
