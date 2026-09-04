import { useState } from 'react';
import type { StructuredLogView } from '../types';

export default function LogPanel({ items, onEvidence, onCorrelation }: {
  items: StructuredLogView[];
  onEvidence: (id: string) => void;
  onCorrelation: (id: string) => void;
}) {
  const [level, setLevel] = useState('all');
  const [expanded, setExpanded] = useState<string | null>(null);
  const visible = items.filter(item => level === 'all' || item.level === level);
  return <section className="ops-panel logs-panel" aria-label="结构化日志">
    <div className="panel-heading"><h2>结构化日志 <small>{visible.length} 条</small></h2>
      <label>级别 <select value={level} onChange={event => setLevel(event.target.value)}>
        <option value="all">全部级别</option>{['info', 'warning', 'error', 'debug', 'critical', 'trace'].map(value =>
          <option key={value} value={value}>{value.toUpperCase()}</option>)}
      </select></label></div>
    <div className="log-columns"><span>级别 / 时间</span><span>来源</span><span>消息与关联链路</span></div>
    {!visible.length && <p className="empty">没有符合条件的日志。可切换级别或清除顶部筛选。</p>}
    {visible.map(item => <article key={item.eventId} className={`log-entry level-${item.level}`}>
      <button className="log-row" aria-expanded={expanded === item.eventId}
        onClick={() => setExpanded(expanded === item.eventId ? null : item.eventId)}>
        <span><b className="log-level">{item.level.toUpperCase()}</b><time>{item.emittedAt.slice(11, 19)} UTC</time></span>
        <span className="log-source">{item.sourceTool || item.sourceModule}<small className="mode">{item.mode.toUpperCase()}</small></span>
        <span>{item.message}<small>{item.context.jobId} · {item.context.correlationId}　{expanded === item.eventId ? '−' : '+'}</small></span>
      </button>
      {expanded === item.eventId && <div className="log-details">
        <dl>{Object.entries(item.context).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value || '—'}</dd></div>)}</dl>
        <pre>{JSON.stringify(item.fields, null, 2)}</pre>
        <div className="actions"><button onClick={() => onCorrelation(item.context.correlationId)}>仅看此关联链路</button>
          {item.artifactLinks.map(link => <button key={link.artifactId} onClick={() => onEvidence(link.artifactId)}>{link.label} ↗</button>)}
        </div>
      </div>}
    </article>)}
  </section>;
}
