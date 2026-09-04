import type { ReactNode } from "react";

import type { ReviewEditorView } from "../components/reviewPresenter.ts";

import "./review.css";

export interface ReviewSurfaceProps {
  readonly view: ReviewEditorView;
  readonly contextLabel: string;
  readonly onRetry?: () => void;
  readonly children?: ReactNode;
}

export default function ReviewSurface({
  view,
  contextLabel,
  onRetry,
  children,
}: ReviewSurfaceProps) {
  return (
    <section className="review-surface" data-state={view.state} aria-live="polite">
      <header className="review-surface__header">
        <div>
          <h2>{view.title}</h2>
          <span className="review-surface__context">{contextLabel}</span>
        </div>
        <span className={`review-mode review-mode--${view.mode}`}>{view.modeLabel}</span>
      </header>
      <p className="review-surface__message">{view.message}</p>
      {view.conflictMessages.length > 0 && (
        <ul className="review-conflicts" aria-label="评审冲突">
          {view.conflictMessages.map((message) => <li key={message}>{message}</li>)}
        </ul>
      )}
      {view.retryCommandId && onRetry && (
        <button type="button" className="review-action" onClick={onRetry}>重试</button>
      )}
      {view.state === "success" ? children : null}
    </section>
  );
}
