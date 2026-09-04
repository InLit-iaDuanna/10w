import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { reviewRequest, type ReviewData } from "./client.ts";
import type { DemoEntry, DecisionOutcome } from "../generated/api-types.ts";
import { executeReviewCommand } from "./commands.ts";

export function ReviewSidebar({ data, entry, target, onTarget }: {
  data: ReviewData; entry: DemoEntry; target: string; onTarget: (id: string) => void;
}) {
  const [body, setBody] = useState("");
  const [rationale, setRationale] = useState("");
  const [outcome, setOutcome] = useState<DecisionOutcome>("accept");
  const [notice, setNotice] = useState("");
  const cache = useQueryClient();
  const { review } = data;
  const params = { review_id: review.review_id };
  const mutation = useMutation({
    mutationFn: async (action: "comment" | "decision" | "approved" | "rejected") => {
      if (action === "comment") {
        await executeReviewCommand("review.comment.add", review.review_id, {
          body: body.trim(), anchor: { kind: "scene_object", target_id: target,
            review_revision_id: review.review_revision_id, diff_bundle_id: review.diff.diff_bundle_id,
            version: review.target_version },
        });
      } else if (action === "decision") {
        await executeReviewCommand("review.decision.record", review.review_id,
          { outcome, rationale: rationale.trim(), evidence_ids: review.evidence_ids });
      } else {
        await reviewRequest("POST /api/lab/reviews/{review_id}/mock-approval", params,
          { outcome: action, rationale: rationale.trim() });
      }
      return action;
    },
    onSuccess: async action => {
      if (action === "comment") setBody("");
      setNotice(action === "comment" ? "评论已保存，并绑定当前版本与对象。" : "评审记录已保存；没有执行 Git 操作。");
      await cache.invalidateQueries({ queryKey: ["version-review-lab", review.review_id] });
    },
  });
  return <aside className="vr-review"><div className="vr-section-title"><h2>协作评审</h2><span className="vr-avatar">我</span></div>
    <p className="vr-muted">本地评审员 · user.demo-reviewer</p>
    <form onSubmit={event => { event.preventDefault(); mutation.mutate("comment"); }}>
      <label>评论锚点<select value={target} onChange={event => onTarget(event.target.value)}>{entry.inputs.target_ids?.map(id => <option key={id}>{id}</option>)}</select></label>
      <small>目标版本 {review.target_version.commit_id.slice(0, 8)} · 修订 {review.revision}</small>
      <label>添加评论<textarea value={body} onChange={event => setBody(event.target.value)} maxLength={20000} placeholder="记录观察、问题或修改建议…" /></label>
      <button className="vr-primary" disabled={!body.trim() || mutation.isPending || !target}>发布锚定评论</button>
    </form>
    <div className="vr-comment-list">{data.comments.length === 0 ? <p className="vr-muted">还没有评论。选择对象，开始这次评审。</p> : data.comments.map(comment => <article key={comment.comment_id}><small>{comment.author_id} · MOCK</small><p>{comment.body}</p><code>{comment.anchor.target_id}</code><small>{new Date(comment.created_at).toLocaleString("zh-CN")}</small></article>)}</div>
    <h3>提交评审意见</h3><label>决策<select value={outcome} onChange={event => setOutcome(event.target.value as DecisionOutcome)}><option value="accept">接受变更</option><option value="request_changes">要求修改</option><option value="block">阻断评审</option></select></label>
    <label>理由 / 证据说明<textarea value={rationale} onChange={event => setRationale(event.target.value)} maxLength={10000} placeholder="说明你的评审理由…" /></label>
    <button disabled={!rationale.trim() || mutation.isPending} onClick={() => mutation.mutate("decision")}>记录决策</button>
    <h3>模拟审批</h3><p className="vr-muted">绑定当前评审、差异与 Git 版本。不会替代正式审批或触发发布。</p>
    <div className="vr-actions"><button disabled={!rationale.trim() || mutation.isPending} onClick={() => mutation.mutate("approved")}>MOCK 通过</button><button disabled={!rationale.trim() || mutation.isPending} onClick={() => mutation.mutate("rejected")}>MOCK 拒绝</button></div>
    {mutation.isPending && <p role="status">正在保存…</p>}
    {mutation.isError && <p className="vr-error" role="alert">{mutation.error.message}</p>}
    {notice && <p role="status" className="vr-good">{notice}</p>}
  </aside>;
}
