import type { ConversationCard, SuggestedCommand } from "./cards.ts";
import type { ExecutionMode } from "../contracts/executionMode.ts";
import type {
  ConversationMessage,
  ConversationScope,
} from "./types.ts";

export interface ConversationRequest {
  conversationId: string;
  scope: ConversationScope;
  userMessage: ConversationMessage;
  retryOfMessageId?: string;
}

export type ConversationStreamEvent =
  | { type: "text_delta"; text: string }
  | { type: "card_added"; card: ConversationCard }
  | { type: "completed" };

export interface ConversationRun {
  runId: string;
  mode: ExecutionMode;
  events: AsyncIterable<ConversationStreamEvent>;
}

export interface ConversationTransport {
  readonly availabilityMode: ExecutionMode;
  start(
    request: ConversationRequest,
    signal: AbortSignal,
  ): Promise<ConversationRun>;
}

export interface ConversationTransportFailureShape {
  code: string;
  message: string;
  retryable: boolean;
  missingPermissions: string[];
  missingIntegrations: string[];
  suggestedActions: SuggestedCommand[];
}

export class ConversationTransportError extends Error {
  readonly code: string;
  readonly retryable: boolean;
  readonly missingPermissions: string[];
  readonly missingIntegrations: string[];
  readonly suggestedActions: SuggestedCommand[];

  constructor(failure: ConversationTransportFailureShape) {
    super(failure.message);
    this.name = "ConversationTransportError";
    this.code = failure.code;
    this.retryable = failure.retryable;
    this.missingPermissions = failure.missingPermissions;
    this.missingIntegrations = failure.missingIntegrations;
    this.suggestedActions = failure.suggestedActions;
  }
}

export function isConversationTransportError(
  value: unknown,
): value is ConversationTransportError {
  return value instanceof ConversationTransportError;
}
