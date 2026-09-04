import { presentReview } from "../components/reviewPresenter.ts";
import { useReview, useReviewActivity } from "../hooks/useReview.ts";
import ReviewSurface from "./ReviewSurface.tsx";
import {
  errorCode,
  resolveReviewBinding,
  type ReviewEditorRuntimeProps,
} from "./runtime.ts";

export default function ActivityEditor(props: ReviewEditorRuntimeProps) {
  const canRead = props.permissions.has("review:read");
  const binding = resolveReviewBinding(props);
  const review = useReview(
    props.api,
    binding.reviewId,
    canRead,
    binding.reviewRevisionId,
  );
  const activity = useReviewActivity(props.api, binding.reviewId, canRead);
  const view = presentReview({
    loading: review.isLoading || activity.isLoading,
    hasPermission: canRead,
    gitConnected: props.gitConnected,
    review: review.data ?? null,
    errorCode: errorCode(review.error ?? activity.error),
  });

  const retry = () => {
    void review.refetch();
    void activity.refetch();
  };
  const visibleActivity = binding.reviewRevisionId
    ? activity.data?.filter(
        (item) => item.review_revision_id === binding.reviewRevisionId,
      )
    : activity.data;

  return (
    <ReviewSurface
      view={view}
      contextLabel={
        binding.reviewRevisionId
          ? `追加式活动 · 已固定 ${binding.reviewRevisionId}`
          : "追加式活动记录"
      }
      onRetry={retry}
    >
      {visibleActivity?.length ? (
        <ol className="review-activity">
          {visibleActivity.map((item) => (
            <li key={item.activity_id}>
              <time dateTime={item.created_at}>{item.created_at}</time>
              <span>{item.summary}</span>
              <small>{item.mode.toUpperCase()}</small>
            </li>
          ))}
        </ol>
      ) : (
        <p className="review-surface__hint">暂无协作活动。</p>
      )}
    </ReviewSurface>
  );
}
