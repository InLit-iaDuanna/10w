import type { ConversationStorageFailure } from "./repository.ts";
import type { ConversationRecord } from "./types.ts";

export type IdFactory = (
  kind: "conversation" | "message" | "card",
) => string;

export type UtcClock = () => string;

export type ConversationInitializeResult =
  | { status: "ready"; record: ConversationRecord; source: "stored" | "new" }
  | { status: "failed"; error: ConversationStorageFailure };

export type ConversationOperationResult =
  | {
      status: "completed" | "cancelled" | "failed";
      assistantMessageId: string;
      storageFailure?: ConversationStorageFailure;
    }
  | {
      status: "rejected";
      code:
        | "NOT_INITIALIZED"
        | "STREAM_ALREADY_RUNNING"
        | "EMPTY_MESSAGE"
        | "MESSAGE_NOT_RETRYABLE";
      message: string;
    };

export function webCryptoIdFactory(
  kind: "conversation" | "message" | "card",
): string {
  if (!globalThis.crypto?.randomUUID) {
    throw new Error("生成稳定本地 ID 需要 Web Crypto randomUUID。");
  }

  const prefixes = {
    conversation: "cnv",
    message: "msg",
    card: "card",
  } as const;
  return `${prefixes[kind]}_${globalThis.crypto.randomUUID()}`;
}

export function utcClock(): string {
  return new Date().toISOString();
}
