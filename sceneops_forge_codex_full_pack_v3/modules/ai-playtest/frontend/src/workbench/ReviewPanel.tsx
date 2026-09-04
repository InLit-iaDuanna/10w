import { useState } from "react";
import { sourceRecords, type ReviewExample, type LocalReview, type ProposalDraft } from "./evidence.ts";

export function ReviewPanel({ issue, review, proposal, onReview, onProposal }: {
  issue: ReviewExample; review?: LocalReview; proposal?: ProposalDraft;
  onReview: (review: LocalReview) => void; onProposal: (proposal: ProposalDraft) => void;
}) {
  const source = sourceRecords.find(record => record.source_record_id === issue.sourceId);
  const [note, setNote] = useState("");
  const [previousValue, setPreviousValue] = useState("Default");
  const [proposedValue, setProposedValue] = useState("");
  const [rationale, setRationale] = useState("");
  const [expectedResult, setExpectedResult] = useState("");
  const [validationPlan, setValidationPlan] = useState("由 owning module 审批后，在获准环境复核同一测试配置。");
  const [rollbackPlan, setRollbackPlan] = useState("由 owning module 恢复变更前值。");
  function recordReview(decision: LocalReview["decision"]) {
    onReview({ decision, note: note.trim(), reviewedAt: new Date().toISOString() });
  }
  return <section className="ap-review">
    <div className="ap-section-title"><h2>问题回钉</h2><span className="ap-badge">MOCK</span></div>
    <h3>{issue.title}</h3><code>{issue.id}</code>
    <p>{issue.reason}</p>
    <dl><dt>候选状态</dt><dd>{source ? `已匹配 · ${Math.round(issue.confidence * 100)}%（样例分值）` : "未解析"}</dd>
      <dt>源目标</dt><dd>{source?.target_id ?? "没有唯一目标"}</dd>
      <dt>所属模块</dt><dd>{source?.owning_module ?? "—"}</dd>
      <dt>构建版本</dt><dd>{source?.source_version ?? "—"}</dd>
      <dt>源码定位</dt><dd>{source?.locator ?? "—"}</dd></dl>
    {source && <details><summary>查看版本化源记录</summary><pre>{JSON.stringify(source, null, 2)}</pre></details>}
    <p className="ap-muted">源记录来自 fixture 目录；本工作台没有真实 Unity 源码。审阅标记仅保留在当前页面，刷新即清空。</p>
    {review ? <div className="ap-notice"><strong>{review.decision === "confirmed" ? "已模拟确认" : "已模拟拒绝"}</strong><p>{review.note}</p><small>{review.reviewedAt} · 本地演示用户</small></div>
      : <><label>审阅意见<textarea value={note} onChange={e => setNote(e.target.value)} placeholder="记录核对依据或拒绝原因" /></label>
        <div className="ap-actions"><button disabled={!source || !note.trim()} onClick={() => recordReview("confirmed")}>模拟确认回钉</button><button disabled={!note.trim()} onClick={() => recordReview("rejected")}>模拟拒绝</button></div></>}
    <div className="ap-section-title"><h2>修复提案</h2><span className="ap-badge planned">PLANNED</span></div>
    {proposal ? <><p role="status">提案草稿已保存，尚未提交或执行。</p><pre>{JSON.stringify(proposal, null, 2)}</pre></>
      : review?.decision === "confirmed" && source ? <form onSubmit={event => {
        event.preventDefault();
        onProposal({ id: `draft.${issue.id}`, sourceReviewId: issue.id, targetId: source.target_id,
          owningModule: source.owning_module, baseVersion: source.source_version,
          previousValue: previousValue.trim(), proposedValue: proposedValue.trim(), rationale: rationale.trim(),
          expectedResult: expectedResult.trim(), validationPlan: validationPlan.trim(), rollbackPlan: rollbackPlan.trim(),
          risk: "medium", approvalRequirements: [source.owning_module, "人工审批"], executionMode: "planned", submitted: false });
      }}>
        <label>变更前值<input required value={previousValue} onChange={e => setPreviousValue(e.target.value)} /></label>
        <label>建议值<input required value={proposedValue} onChange={e => setProposedValue(e.target.value)} placeholder="例如 Interactable" /></label>
        <label>修改理由<textarea required value={rationale} onChange={e => setRationale(e.target.value)} /></label>
        <label>预期结果<input required value={expectedResult} onChange={e => setExpectedResult(e.target.value)} /></label>
        <label>验证计划<textarea required value={validationPlan} onChange={e => setValidationPlan(e.target.value)} /></label>
        <label>回滚计划<textarea required value={rollbackPlan} onChange={e => setRollbackPlan(e.target.value)} /></label>
        <button className="primary" disabled={!proposedValue.trim() || proposedValue.trim() === previousValue.trim() || !rationale.trim() || !expectedResult.trim() || !validationPlan.trim() || !rollbackPlan.trim()}>保存提案草稿</button>
      </form> : <p className="ap-muted">先模拟确认唯一回钉，再填写提案。真实 ChangeSet 的审批和派发需接入所属模块。</p>}
  </section>;
}
