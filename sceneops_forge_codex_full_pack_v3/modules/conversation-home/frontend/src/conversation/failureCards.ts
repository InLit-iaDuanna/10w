import type { ExecutionMode } from "../contracts/executionMode.ts";
import type { ErrorCard } from "./cards.ts";
import { isConversationTransportError } from "./transport.ts";

function cardId(messageId: string, createCardId: () => string): string {
  return `${createCardId()}_${messageId.slice(4)}`;
}

export function createCancelledCard(
  messageId: string,
  mode: ExecutionMode,
  createCardId: () => string,
): ErrorCard {
  return {
    cardId: cardId(messageId, createCardId),
    kind: "error",
    mode,
    code: "STREAM_CANCELLED",
    message: "响应已取消，可从该消息重试。",
    retryable: true,
    missingPermissions: [],
    missingIntegrations: [],
    suggestedActions: [],
  };
}

export function createInterruptedCard(
  messageId: string,
  mode: ExecutionMode,
  createCardId: () => string,
): ErrorCard {
  return {
    ...createCancelledCard(messageId, mode, createCardId),
    code: "STREAM_INTERRUPTED",
    message: "上次响应在完成前中断，可从该消息重试。",
  };
}

export function createFailureCard(
  messageId: string,
  mode: ExecutionMode,
  error: unknown,
  createCardId: () => string,
): ErrorCard {
  const transportFailure = isConversationTransportError(error) ? error : null;
  return {
    cardId: cardId(messageId, createCardId),
    kind: "error",
    mode,
    code: transportFailure?.code ?? "CONVERSATION_STREAM_FAILED",
    message: transportFailure?.message ?? "对话响应失败。",
    retryable: transportFailure?.retryable ?? false,
    missingPermissions: transportFailure?.missingPermissions ?? [],
    missingIntegrations: transportFailure?.missingIntegrations ?? [],
    suggestedActions: transportFailure?.suggestedActions ?? [],
  };
}
