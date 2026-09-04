import type { ExecutionMode } from "../contracts/executionMode.ts";
import type {
  ConversationRecord,
  ConversationScope,
} from "./types.ts";
import { isConversationRecord } from "./recordValidation.ts";

export { isConversationRecord } from "./recordValidation.ts";

export interface KeyValueStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface ConversationStorageFailure {
  code: "CONVERSATION_STORAGE_INVALID" | "CONVERSATION_STORAGE_UNAVAILABLE";
  message: string;
  scope: ConversationScope;
}

export type ConversationLoadResult =
  | { status: "loaded"; record: ConversationRecord }
  | { status: "missing" }
  | { status: "failed"; error: ConversationStorageFailure };

export type ConversationSaveResult =
  | { status: "saved" }
  | { status: "failed"; error: ConversationStorageFailure };

export function createConversationRecord(
  scope: ConversationScope,
  conversationId: string,
  mode: ExecutionMode,
  now: string,
): ConversationRecord {
  return {
    schemaVersion: 1,
    conversationId,
    scope,
    messages: [],
    executionMode: mode,
    updatedAt: now,
    activeRunId: null,
  };
}

function scopeKey(scope: ConversationScope): string {
  const identity = scope.kind === "project" ? scope.projectId : scope.sessionId;
  return `sceneops:conversation-home:v1:${scope.kind}:${encodeURIComponent(identity)}`;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "未知存储错误";
}

export class ConversationRepository {
  readonly #persistentStorage: KeyValueStorage;
  readonly #temporaryStorage: KeyValueStorage;

  constructor(
    persistentStorage: KeyValueStorage,
    temporaryStorage: KeyValueStorage,
  ) {
    this.#persistentStorage = persistentStorage;
    this.#temporaryStorage = temporaryStorage;
  }

  load(scope: ConversationScope): ConversationLoadResult {
    try {
      const serialized = this.#storage(scope).getItem(scopeKey(scope));
      if (serialized === null) {
        return { status: "missing" };
      }

      let candidate: unknown;
      try {
        candidate = JSON.parse(serialized);
      } catch {
        return {
          status: "failed",
          error: {
            code: "CONVERSATION_STORAGE_INVALID",
            message: "保存的对话记录不是有效 JSON。",
            scope,
          },
        };
      }
      if (!isConversationRecord(candidate) || !sameScope(candidate.scope, scope)) {
        return {
          status: "failed",
          error: {
            code: "CONVERSATION_STORAGE_INVALID",
            message: "保存的对话记录不符合 schema 或 scope 不匹配。",
            scope,
          },
        };
      }

      return { status: "loaded", record: candidate };
    } catch (error) {
      return {
        status: "failed",
        error: {
          code: "CONVERSATION_STORAGE_UNAVAILABLE",
          message: `无法读取对话记录：${errorMessage(error)}`,
          scope,
        },
      };
    }
  }

  save(record: ConversationRecord): ConversationSaveResult {
    const scope = record.scope;
    if (!isConversationRecord(record)) {
      return {
        status: "failed",
        error: {
          code: "CONVERSATION_STORAGE_INVALID",
          message: "拒绝保存不符合 schema 的对话记录。",
          scope,
        },
      };
    }

    try {
      this.#storage(record.scope).setItem(
        scopeKey(record.scope),
        JSON.stringify(record),
      );
      return { status: "saved" };
    } catch (error) {
      return {
        status: "failed",
        error: {
          code: "CONVERSATION_STORAGE_UNAVAILABLE",
          message: `无法保存对话记录：${errorMessage(error)}`,
          scope: record.scope,
        },
      };
    }
  }

  clear(scope: ConversationScope): ConversationSaveResult {
    try {
      this.#storage(scope).removeItem(scopeKey(scope));
      return { status: "saved" };
    } catch (error) {
      return {
        status: "failed",
        error: {
          code: "CONVERSATION_STORAGE_UNAVAILABLE",
          message: `无法清除对话记录：${errorMessage(error)}`,
          scope,
        },
      };
    }
  }

  #storage(scope: ConversationScope): KeyValueStorage {
    return scope.kind === "project"
      ? this.#persistentStorage
      : this.#temporaryStorage;
  }
}

function sameScope(left: ConversationScope, right: ConversationScope): boolean {
  return left.kind === right.kind &&
    (left.kind === "project"
      ? left.projectId === (right as { kind: "project"; projectId: string }).projectId
      : left.sessionId ===
        (right as { kind: "pre_project"; sessionId: string }).sessionId);
}
