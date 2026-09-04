import { presentConversationSummary, presentReview } from "../components/reviewPresenter.ts";
import {
  useActiveLocks,
  useReview,
  useReviewConversation,
  useReviewSummary,
} from "../hooks/useReview.ts";
import ReviewSurface from "./ReviewSurface.tsx";
import {
  errorCode,
  resolveReviewBinding,
  type ReviewEditorRuntimeProps,
} from "./runtime.ts";

export default function ReviewSessionEditor(props: ReviewEditorRuntimeProps) {
  const canRead = props.permissions.has("review:read");
  const binding = resolveReviewBinding(props);
  const review = useReview(
    props.api,
    binding.reviewId,
    canRead,
    binding.reviewRevisionId,
  );
  const summary = useReviewSummary(
    props.api,
    binding.reviewId,
    canRead,
    binding.reviewRevisionId,
  );
  const conversation = useReviewConversation(
    props.api,
    binding.reviewId,
    canRead,
  );
  const locks = useActiveLocks(
    props.api,
    review.data?.project_id ?? null,
    canRead,
  );
  const view = presentReview({
    loading: review.isLoading || summary.isLoading || conversation.isLoading,
    hasPermission: canRead,
    gitConnected: props.gitConnected,
    review: review.data ?? null,
    errorCode: errorCode(
      review.error ?? summary.error ?? conversation.error,
    ),
  });

  const retry = () => {
    void review.refetch();
    void summary.refetch();
    void conversation.refetch();
    void locks.refetch();
  };
  const revisionId = review.data?.review_revision_id;
  const comments = conversation.data?.comments.filter(
    (item) => item.anchor.review_revision_id === revisionId,
  ) ?? [];
  const decisions = conversation.data?.decisions.filter(
    (item) => item.review_revision_id === revisionId,
  ) ?? [];
  const approvals = conversation.data?.approvals.filter(
    (item) => item.review_revision_id === revisionId,
  ) ?? [];
  const approvalIds = new Set(approvals.map((item) => item.approval_id));
  const releaseLinks = conversation.data?.releaseLinks.filter(
    (item) => approvalIds.has(item.approval_id),
  ) ?? [];
  const contextLabel = binding.reviewRevisionId
    ? `已固定 · ${binding.reviewRevisionId}`
    : "评论 · 分配 · 决定 · 审批";

  return (
    <ReviewSurface view={view} contextLabel={contextLabel} onRetry={retry}>
      {summary.data && (
        <pre className="review-summary">
          {presentConversationSummary(summary.data)}
        </pre>
      )}
      <div className="review-collaboration-grid">
        <ReviewItems
          title="评论"
          items={comments.map((item) => `${item.author_id}：${item.body}`)}
        />
        <ReviewItems
          title="分配"
          items={(conversation.data?.assignments ?? []).map(
            (item) => `${item.reviewer_id} · ${item.action}`,
          )}
        />
        <ReviewItems
          title="决定"
          items={decisions.map((item) => `${item.outcome}：${item.rationale}`)}
        />
        <ReviewItems
          title="审批与证据"
          items={approvals.map(
            (item) =>
              `${item.outcome} · ${item.approver_id} · ${item.evidence_ids.join("、")}`,
          )}
        />
        <ReviewItems
          title="二进制锁"
          items={locks.error
            ? ["锁服务不可用；本地投影未被当作远端事实。"]
            : (locks.data ?? []).map(
                (item) => `${item.path} · ${item.owner_id}`,
              )}
        />
        <ReviewItems
          title="发布链接"
          items={releaseLinks.map(
            (item) => `${item.release_id} · ${item.evidence_ids.join("、")}`,
          )}
        />
      </div>
      <p className="review-surface__hint">
        修改动作统一通过 typed command registry 执行。
      </p>
    </ReviewSurface>
  );
}

function ReviewItems({
  title,
  items,
}: {
  title: string;
  items: readonly string[];
}) {
  return (
    <section className="review-collaboration-list">
      <h3>{title}</h3>
      {items.length ? (
        <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
      ) : (
        <p>暂无</p>
      )}
    </section>
  );
}
