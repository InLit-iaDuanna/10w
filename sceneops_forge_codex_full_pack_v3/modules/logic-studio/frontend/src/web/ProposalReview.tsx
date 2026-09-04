import './logic.css';
import type { ChangeSet, CodeChangeSet, GraphProposalResponse } from './api-types.ts';

export function ProposalReview({ changeSet, diff, onExport }: { changeSet: ChangeSet | CodeChangeSet; diff?: GraphProposalResponse['diff']; onExport: (name: string, data: unknown) => void }) {
  const target = 'target' in changeSet ? changeSet.target.object_ids : changeSet.target_objects;
  return <section className="proposal-review">
    <div className="panel-header"><strong>ChangeSet / 待审批提案</strong><span className="badge planned">planned · {changeSet.status}</span></div>
    <div className="proposal-body"><code>{changeSet.change_set_id}</code><p>{changeSet.rationale}</p>
      <dl><dt>基础版本</dt><dd>{changeSet.base_version}</dd><dt>影响对象</dt><dd>{target?.join(', ')}</dd><dt>预期结果</dt><dd>{changeSet.expected_result}</dd><dt>风险</dt><dd>{changeSet.risk}</dd><dt>审批权限</dt><dd>{changeSet.approval_requirements?.map(requirement => requirement.permission).join(' / ')}</dd></dl>
      <div className="semantic-diff">{diff && <><h4>变更明细 · {diff.entries.length} 项</h4>{diff.entries.map(entry => <p key={`${entry.entity_type}:${entry.entity_id}`}><code>{entry.entity_type} / {entry.entity_id}</code> · {entry.change}{entry.previous?.label !== entry.proposed?.label && <> · {String(entry.previous?.label ?? '∅')} → {String(entry.proposed?.label ?? '∅')}</>}</p>)}</>}</div>
      <div className="diff-columns"><section><h4>修改前</h4><pre>{JSON.stringify(changeSet.previous_values, null, 2)}</pre></section><section><h4>提议修改后</h4><pre>{JSON.stringify(changeSet.proposed_values, null, 2)}</pre></section></div>
      <details><summary>验证与回滚计划（尚未执行）</summary><p>{changeSet.validation_plan.join('；')}</p><p>{changeSet.rollback_plan.join('；')}</p></details>
      <div className="actions"><button onClick={() => onExport('changeset.json', changeSet)}>导出 ChangeSet</button><span className="badge blocked">blocked · 写回需要正式审批与外部适配器</span></div>
    </div>
  </section>;
}
