import { presentReview } from "../components/reviewPresenter.ts";
import { useReview } from "../hooks/useReview.ts";
import type { ReviewSession } from "../generated/api-types.ts";
import type { ReviewLayer } from "../state/reviewEditorState.ts";
import ReviewSurface from "./ReviewSurface.tsx";
import { errorCode, resolveReviewBinding, type ReviewEditorRuntimeProps } from "./runtime.ts";

const layerLabels: Record<ReviewLayer, string> = {
  file: "文件",
  semantic: "场景语义",
  visual: "固定相机视觉",
  behavior: "玩家行为",
};

export default function VersionDiffEditor(props: ReviewEditorRuntimeProps) {
  const canLoad = props.permissions.has("review:read");
  const binding = resolveReviewBinding(props);
  const query = useReview(
    props.api,
    binding.reviewId,
    canLoad,
    binding.reviewRevisionId,
  );
  const view = presentReview({
    loading: query.isLoading,
    hasPermission: props.permissions.has("review:read"),
    gitConnected: props.gitConnected,
    review: query.data ?? null,
    errorCode: errorCode(query.error),
  });
  const contextLabel = props.localState.contextBinding.mode === "pinned"
    ? `已固定 · ${props.localState.contextBinding.reviewRevisionId}`
    : "跟随全局上下文";
  const review = query.data;

  return (
    <ReviewSurface
      view={view}
      contextLabel={contextLabel}
      onRetry={() => void query.refetch()}
    >
      {review && (
        <div className="review-diff">
          <nav className="review-layer-tabs" aria-label="四层差异">
            {(Object.keys(layerLabels) as ReviewLayer[]).map((layer) => (
              <button
                type="button"
                key={layer}
                aria-pressed={props.localState.selectedLayer === layer}
                onClick={() => props.updateLocalState({ selectedLayer: layer })}
              >
                {layerLabels[layer]}
              </button>
            ))}
          </nav>
          <LayerResult review={review} layer={props.localState.selectedLayer} />
        </div>
      )}
    </ReviewSurface>
  );
}

function LayerResult({ review, layer }: { review: ReviewSession; layer: ReviewLayer }) {
  const diff = review.diff;
  if (layer === "file") {
    return (
      <section className="review-layer-result">
        <LayerState state={diff.file.state} mode={diff.file.mode} reason={diff.file.failure_reason} />
        <ul>
          {diff.file.changes.map((change) => (
            <li key={`${change.kind}:${change.old_path ?? ""}:${change.path}`}>
              <code>{change.path}</code>
              <span>{change.kind}</span>
              <small>
                {change.binary
                  ? "二进制"
                  : `+${change.additions ?? 0} / -${change.deletions ?? 0}`}
              </small>
            </li>
          ))}
        </ul>
        <p>{diff.file.lfs_pointers.length} 个 Git LFS 指针。</p>
      </section>
    );
  }
  if (layer === "semantic") {
    return (
      <section className="review-layer-result">
        <LayerState state={diff.semantic.state} mode={diff.semantic.mode} reason={diff.semantic.failure_reason} />
        <ul>
          {diff.semantic.changes.map((change) => (
            <li key={`${change.entity_id}:${change.path}:${change.kind}`}>
              <code>{change.entity_id}{change.path}</code>
              <span>{change.kind}</span>
              <small>{formatValue(change.before)} → {formatValue(change.after)}</small>
            </li>
          ))}
        </ul>
      </section>
    );
  }
  if (layer === "visual") {
    return (
      <section className="review-layer-result">
        <LayerState state={diff.visual.state} mode={diff.visual.mode} reason={diff.visual.failure_reason} />
        <dl>
          <dt>固定相机</dt><dd>{diff.visual.camera_id ?? "未提供"}</dd>
          <dt>样本变化</dt>
          <dd>{diff.visual.changed_samples ?? 0} / {diff.visual.sample_count ?? 0}</dd>
          <dt>平均绝对误差</dt><dd>{diff.visual.mean_absolute_error ?? "不可用"}</dd>
          <dt>最大绝对误差</dt><dd>{diff.visual.maximum_absolute_error ?? "不可用"}</dd>
          <dt>证据</dt>
          <dd>{diff.visual.base_artifact_id ?? "—"} → {diff.visual.target_artifact_id ?? "—"}</dd>
        </dl>
      </section>
    );
  }
  return (
    <section className="review-layer-result">
      <LayerState state={diff.behavior.state} mode={diff.behavior.mode} reason={diff.behavior.failure_reason} />
      <ul>
        {diff.behavior.changes.map((change) => (
          <li key={`${change.category}:${change.key}`}>
            <code>{change.category}:{change.key}</code>
            <small>{formatValue(change.before)} → {formatValue(change.after)}</small>
          </li>
        ))}
      </ul>
      <p>运行证据：{diff.behavior.before_run_id ?? "—"} → {diff.behavior.after_run_id ?? "—"}</p>
    </section>
  );
}

function LayerState({ state, mode, reason }: { state: string; mode: string; reason?: string | null }) {
  return (
    <p className="review-layer-state">
      状态：{state} · {mode.toUpperCase()}{reason ? ` · ${reason}` : ""}
    </p>
  );
}

function formatValue(value: unknown): string {
  if (value === undefined) return "未提供";
  return typeof value === "string" ? value : JSON.stringify(value) ?? String(value);
}
