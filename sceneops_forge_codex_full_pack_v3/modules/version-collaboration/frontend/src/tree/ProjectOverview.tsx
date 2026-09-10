import { useState } from 'react';
import type { VersionTreeState } from '../generated/api-types';
import './project-overview.css';

const stages = [['idea', '创意'], ['grill', '需求对齐'], ['outline', '策划'], ['stack', '技术方案'], ['cards', '制作规划']];
type Props = { data: VersionTreeState; onCommit: (id: string) => void; onBranch: (name: string) => void };
export function ProjectOverview({ data, onCommit, onBranch }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filter, setFilter] = useState('all');
  const progress = data.progress;
  const cards = progress?.cards ?? [];
  const currentStage = stages.findIndex(([id]) => id === progress?.stage);
  const visibleCards = cards.filter(card => filter === 'all' || (filter === 'branched' ? card.branches.length > 0 : card.branches.length === 0));
  return <div className="po-content">
    <div className="po-metrics">
      <div><strong>{progress?.confirmed_versions ?? '—'}</strong><span>策划版本</span></div>
      <div><strong>{progress?.planned_cards ?? '—'}</strong><span>制作卡片</span></div>
      <div><strong>{data.commits.length}</strong><span>版本提交</span></div>
    </div>
    <section className="po-section"><div className="po-section-title"><h3>项目进程</h3><span>{currentStage >= 0 ? stages[currentStage][1] : '尚未关联策划'}</span></div>
      <ol className="po-stages">{stages.map(([id, label], index) => <li key={id} className={index === currentStage ? 'is-current' : index < currentStage ? 'is-past' : ''} aria-current={index === currentStage ? 'step' : undefined}><span>{index < currentStage ? '✓' : String(index + 1).padStart(2, '0')}</span><b>{label}</b></li>)}</ol>
      <p className="po-note">制作 → 验证 → 发布 · 后续阶段等待执行证据</p>
    </section>
    <section className="po-section"><div className="po-section-title"><h3>制作内容 <small>{cards.length}</small></h3><select aria-label="筛选制作卡片" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">全部内容</option><option value="branched">已关联分支</option><option value="planned">待建立分支</option></select></div>
      {!progress ? <p className="po-empty">尚未关联项目策划。提交记录仍可在版本历史中查看。</p> : !visibleCards.length ? <p className="po-empty">{cards.length ? '没有符合筛选条件的卡片。' : '尚未生成制作卡片，确认策划后将在这里汇总。'}</p> : <div className="po-cards">{visibleCards.map((card, index) => <article key={card.card_id} className={expanded === card.card_id ? 'is-expanded' : ''}>
        <button className="po-card-toggle" aria-expanded={expanded === card.card_id} onClick={() => setExpanded(expanded === card.card_id ? null : card.card_id)}><span className="po-card-number">{String(index + 1).padStart(2, '0')}</span><span className="po-card-title"><b>{card.title}</b><small>{card.branches.length ? `${card.branches.length} 个关联分支` : '等待开始制作'}</small></span><span className="po-status">计划中</span><span className="po-chevron">⌄</span></button>
        {expanded === card.card_id && <div className="po-card-detail"><p>{card.description}</p><h4>验收目标</h4><p>{card.acceptance}</p>{card.dependencies.length > 0 && <><h4>前置内容</h4><p>{card.dependencies.map(id => cards.find(item => item.card_id === id)?.title ?? id).join(' · ')}</p></>}{card.branches.map(name => <button key={name} className="po-branch-link" onClick={() => onBranch(name)}>⑂ {name} <span>查看版本 →</span></button>)}<small>计划与分支记录不代表已完成制作。</small></div>}
      </article>)}</div>}
    </section>
    <section className="po-section"><div className="po-section-title"><h3>版本里程碑</h3><span>已确认的项目方向</span></div>
      {!progress?.versions?.length ? <p className="po-empty">确认后的策划版本将在这里保留。</p> : <div className="po-milestones">{[...progress.versions].reverse().map(version => <button key={version.number} disabled={!version.commit || !data.commits.some(commit => commit.commit_id === version.commit)} onClick={() => version.commit && onCommit(version.commit)}><span className="po-version">v{version.number}</span><span><b>{version.title}</b><small>{new Date(version.confirmed_at).toLocaleDateString('zh-CN')} · 策划已确认</small></span><span>↗</span></button>)}</div>}
    </section>
    <div className={`po-workspace ${data.conflicted ? 'has-conflict' : ''}`}><span className="po-state-dot"/><span>{data.conflicted ? '存在合并冲突，请先处理' : data.dirty ? `${data.changes.length} 个文件有待提交的修改` : '工作区已同步'}<small>{data.version.branch ?? '游离 HEAD'}</small></span><button onClick={() => onCommit(data.version.commit_id)}>查看变更 →</button></div>
  </div>;
}
