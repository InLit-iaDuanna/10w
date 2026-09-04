import React from "react";
import type { PreparedAction } from "../assistant-actions/coordinator.ts";
import type { AssistantAction } from "../assistant-actions/types.ts";
import type {
  ConversationCard,
  ErrorCard,
  SuggestedCommand,
} from "../conversation/cards.ts";
import { ModeBadge } from "./ModeBadge.tsx";

export interface ConversationCardViewProps {
  card: ConversationCard;
  preparedAction?: PreparedAction;
  onPrepareAction(action: AssistantAction): void;
  onExecuteAction(actionId: string, confirmLayout: boolean): void;
  onCancelAction(actionId: string): void;
  onRetry?(): void;
  onSuggestedCommand(command: SuggestedCommand): void;
}

const progressStateLabels = {
  queued: "已排队",
  running: "运行中",
  waiting_approval: "等待审批",
  succeeded: "已通过",
  failed: "失败",
  cancelled: "已取消",
  blocked: "受阻",
} as const;

const approvalRiskLabels = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "关键",
} as const;

const approvalStateLabels = {
  requested: "已请求",
  waiting: "等待中",
  approved: "已批准",
  rejected: "已拒绝",
  expired: "已过期",
} as const;

function ErrorDetails({ card }: { card: ErrorCard }) {
  return (
    <>
      <p>{card.message}</p>
      {card.missingPermissions.length > 0 && (
        <p>缺少权限：{card.missingPermissions.join("、")}</p>
      )}
      {card.missingIntegrations.length > 0 && (
        <p>缺少集成：{card.missingIntegrations.join("、")}</p>
      )}
    </>
  );
}

function ErrorActions({
  card,
  onRetry,
  onSuggestedCommand,
}: {
  card: ErrorCard;
  onRetry?(): void;
  onSuggestedCommand(command: SuggestedCommand): void;
}) {
  if ((!card.retryable || !onRetry) && card.suggestedActions.length === 0) {
    return null;
  }
  return (
    <div className="conversation-card__actions">
      {card.retryable && onRetry && (
        <button type="button" onClick={onRetry}>重试</button>
      )}
      {card.suggestedActions.map((command) => (
        <button
          key={command.commandId}
          type="button"
          onClick={() => onSuggestedCommand(command)}
        >
          {command.title}
        </button>
      ))}
    </div>
  );
}

function ActionControls(props: ConversationCardViewProps & { action: AssistantAction }) {
  const { action, preparedAction } = props;
  if (!preparedAction) {
    return (
      <button type="button" onClick={() => props.onPrepareAction(action)}>
        {action.type === "workbench.open_editor" ? "预览布局" : "检查并继续"}
      </button>
    );
  }

  if (preparedAction.status === "invalid" || preparedAction.status === "unavailable") {
    return (
      <>
        <ErrorDetails card={preparedAction.error} />
        <ErrorActions
          card={preparedAction.error}
          onSuggestedCommand={props.onSuggestedCommand}
        />
      </>
    );
  }

  if (preparedAction.status === "waiting_approval") {
    return <p role="status">等待审批后才能执行。</p>;
  }

  const confirmsLayout = preparedAction.status === "awaiting_confirmation";
  return (
    <div className="conversation-card__actions">
      {confirmsLayout && (
        <div className="conversation-layout-preview" role="status">
          <strong>布局预览</strong>
          <span>{preparedAction.preview.summary}</span>
          <span>{preparedAction.preview.targetDescription}</span>
          <ul>
            {preparedAction.preview.changes.map((change) => (
              <li key={change}>{change}</li>
            ))}
          </ul>
        </div>
      )}
      <button
        type="button"
        onClick={() => props.onExecuteAction(action.actionId, confirmsLayout)}
      >
        {confirmsLayout ? "确认布局并执行" : "执行"}
      </button>
      <button type="button" onClick={() => props.onCancelAction(action.actionId)}>
        取消
      </button>
    </div>
  );
}

export function ConversationCardView(props: ConversationCardViewProps) {
  const { card } = props;
  if (card.kind === "progress") {
    return (
      <section className="conversation-card" aria-label={`运行进度：${card.title}`}>
        <header><strong>{card.title}</strong><ModeBadge mode={card.mode} /></header>
        <ol>
          {card.nodes.map((node) => (
            <li key={node.nodeId} data-state={node.state}>
              <span>{node.label}</span><span>{progressStateLabels[node.state]}</span>
              {node.detail && <small>{node.detail}</small>}
            </li>
          ))}
        </ol>
      </section>
    );
  }

  if (card.kind === "artifact") {
    return (
      <section className="conversation-card" aria-label={`产物：${card.title}`}>
        <header><strong>{card.title}</strong><ModeBadge mode={card.mode} /></header>
        <p>{card.artifactType} · {card.provenance.artifactId}</p>
        {card.previewUrl && (
          <img
            className="conversation-card__artifact-preview"
            src={card.previewUrl}
            alt={`${card.title} 预览`}
            loading="lazy"
          />
        )}
        <small>由 {card.provenance.producingModule} 生成 · {card.provenance.approvalState}</small>
        {card.openAction && <ActionControls {...props} action={card.openAction} />}
      </section>
    );
  }

  if (card.kind === "error") {
    return (
      <section className="conversation-card conversation-card--error" role="alert">
        <header><strong>{card.code}</strong><ModeBadge mode={card.mode} /></header>
        <ErrorDetails card={card} />
        <ErrorActions
          card={card}
          onRetry={props.onRetry}
          onSuggestedCommand={props.onSuggestedCommand}
        />
      </section>
    );
  }

  if (card.kind === "approval") {
    return (
      <section className="conversation-card conversation-card--approval" aria-label="审批">
        <header><strong>{card.title}</strong><ModeBadge mode={card.mode} /></header>
        <p>风险：{approvalRiskLabels[card.risk]} · 状态：{approvalStateLabels[card.state]}</p>
        <p>ChangeSet：{card.changeSetId}</p>
        {card.requestAction && <ActionControls {...props} action={card.requestAction} />}
      </section>
    );
  }

  const action = card.action;
  return (
    <section className="conversation-card" aria-label={card.title}>
      <header><strong>{card.title}</strong><ModeBadge mode={card.mode} /></header>
      {"description" in card && card.description && <p>{card.description}</p>}
      <ActionControls {...props} action={action} />
    </section>
  );
}
