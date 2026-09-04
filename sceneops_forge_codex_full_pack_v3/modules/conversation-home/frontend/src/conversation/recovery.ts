import { createInterruptedCard } from "./failureCards.ts";
import type { ConversationRecord } from "./types.ts";

export function recoverInterruptedMessages(
  record: ConversationRecord,
  now: string,
  createCardId: () => string,
): ConversationRecord {
  const interruptedIds = new Set(
    record.messages
      .filter(
        (message) => message.role === "assistant" && message.status === "streaming",
      )
      .map((message) => message.messageId),
  );
  if (interruptedIds.size === 0) {
    return record;
  }

  return {
    ...record,
    activeRunId: null,
    updatedAt: now,
    messages: record.messages.map((message) =>
      interruptedIds.has(message.messageId)
        ? {
            ...message,
            status: "cancelled" as const,
            cards: [
              ...message.cards,
              createInterruptedCard(message.messageId, message.mode, createCardId),
            ],
          }
        : message,
    ),
  };
}
