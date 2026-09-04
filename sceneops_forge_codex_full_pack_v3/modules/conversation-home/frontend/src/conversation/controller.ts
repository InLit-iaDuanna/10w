import {
  createCancelledCard,
  createFailureCard,
} from "./failureCards.ts";
import {
  ConversationRepository,
  createConversationRecord,
  type ConversationStorageFailure,
} from "./repository.ts";
import { recoverInterruptedMessages } from "./recovery.ts";
import type { ConversationRequest, ConversationTransport } from "./transport.ts";
import {
  utcClock,
  webCryptoIdFactory,
  type ConversationInitializeResult,
  type ConversationOperationResult,
  type IdFactory,
  type UtcClock,
} from "./controllerTypes.ts";
import type {
  ConversationAttachment,
  ConversationMessage,
  ConversationRecord,
  ConversationScope,
} from "./types.ts";

export {
  utcClock,
  webCryptoIdFactory,
  type ConversationInitializeResult,
  type ConversationOperationResult,
  type IdFactory,
  type UtcClock,
} from "./controllerTypes.ts";

function abortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

export class ConversationController {
  readonly #repository: ConversationRepository;
  readonly #transport: ConversationTransport;
  readonly #idFactory: IdFactory;
  readonly #clock: UtcClock;
  readonly #listeners = new Set<(record: ConversationRecord) => void>();
  #record: ConversationRecord | null = null;
  #activeAbortController: AbortController | null = null;

  constructor(
    repository: ConversationRepository,
    transport: ConversationTransport,
    idFactory: IdFactory = webCryptoIdFactory,
    clock: UtcClock = utcClock,
  ) {
    this.#repository = repository;
    this.#transport = transport;
    this.#idFactory = idFactory;
    this.#clock = clock;
  }

  get snapshot(): ConversationRecord | null {
    return this.#record;
  }

  subscribe(listener: (record: ConversationRecord) => void): () => void {
    this.#listeners.add(listener);
    return () => this.#listeners.delete(listener);
  }

  initialize(scope: ConversationScope): ConversationInitializeResult {
    this.cancel();
    this.#activeAbortController = null;
    this.#record = null;
    const loaded = this.#repository.load(scope);
    if (loaded.status === "failed") {
      return loaded;
    }

    if (loaded.status === "loaded") {
      const record = recoverInterruptedMessages(
        loaded.record,
        this.#clock(),
        () => this.#idFactory("card"),
      );
      if (record !== loaded.record) {
        const saved = this.#repository.save(record);
        if (saved.status === "failed") {
          return saved;
        }
      }
      this.#record = record;
      this.#notify();
      return { status: "ready", record, source: "stored" };
    }

    const record = createConversationRecord(
      scope,
      this.#idFactory("conversation"),
      this.#transport.availabilityMode,
      this.#clock(),
    );
    const saved = this.#repository.save(record);
    if (saved.status === "failed") {
      return saved;
    }

    this.#record = record;
    this.#notify();
    return { status: "ready", record, source: "new" };
  }

  async send(
    text: string,
    attachments: ConversationAttachment[] = [],
  ): Promise<ConversationOperationResult> {
    if (!this.#record) {
      return {
        status: "rejected",
        code: "NOT_INITIALIZED",
        message: "对话尚未初始化。",
      };
    }

    if (this.#activeAbortController) {
      return {
        status: "rejected",
        code: "STREAM_ALREADY_RUNNING",
        message: "已有响应正在生成，请先取消。",
      };
    }

    const normalizedText = text.trim();
    if (normalizedText.length === 0 && attachments.length === 0) {
      return {
        status: "rejected",
        code: "EMPTY_MESSAGE",
        message: "消息或附件不能为空。",
      };
    }

    const userMessage: ConversationMessage = {
      messageId: this.#idFactory("message"),
      role: "user",
      body: normalizedText,
      createdAt: this.#clock(),
      mode: this.#transport.availabilityMode,
      status: "complete",
      attachments,
      cards: [],
    };
    this.#appendMessage(userMessage);
    return this.#startAssistantReply(userMessage);
  }

  async retry(assistantMessageId: string): Promise<ConversationOperationResult> {
    if (!this.#record) {
      return {
        status: "rejected",
        code: "NOT_INITIALIZED",
        message: "对话尚未初始化。",
      };
    }

    if (this.#activeAbortController) {
      return {
        status: "rejected",
        code: "STREAM_ALREADY_RUNNING",
        message: "已有响应正在生成，请先取消。",
      };
    }

    const failedReply = this.#record.messages.find(
      (message) =>
        message.messageId === assistantMessageId &&
        message.role === "assistant" &&
        (message.status === "failed" || message.status === "cancelled"),
    );
    const userMessage = failedReply?.replyToMessageId
      ? this.#record.messages.find(
          (message) => message.messageId === failedReply.replyToMessageId,
        )
      : undefined;

    if (!failedReply || !userMessage || userMessage.role !== "user") {
      return {
        status: "rejected",
        code: "MESSAGE_NOT_RETRYABLE",
        message: "只能重试失败或已取消响应对应的用户消息。",
      };
    }

    return this.#startAssistantReply(userMessage, failedReply.messageId);
  }

  cancel(): boolean {
    if (!this.#activeAbortController) {
      return false;
    }

    this.#activeAbortController.abort();
    return true;
  }

  async #startAssistantReply(
    userMessage: ConversationMessage,
    retryOfMessageId?: string,
  ): Promise<ConversationOperationResult> {
    const record = this.#record;
    if (!record) {
      return {
        status: "rejected",
        code: "NOT_INITIALIZED",
        message: "对话尚未初始化。",
      };
    }

    const assistantMessage: ConversationMessage = {
      messageId: this.#idFactory("message"),
      role: "assistant",
      body: "",
      createdAt: this.#clock(),
      mode: this.#transport.availabilityMode,
      status: "streaming",
      replyToMessageId: userMessage.messageId,
      attachments: [],
      cards: [],
    };
    this.#appendMessage(assistantMessage);

    const abortController = new AbortController();
    this.#activeAbortController = abortController;
    const request: ConversationRequest = {
      conversationId: record.conversationId,
      scope: record.scope,
      userMessage,
      retryOfMessageId,
    };

    try {
      const run = await this.#transport.start(request, abortController.signal);
      if (
        abortController.signal.aborted ||
        !this.#isCurrentConversation(record.conversationId)
      ) {
        throw new DOMException("Conversation scope changed", "AbortError");
      }
      this.#updateRecord({ executionMode: run.mode, activeRunId: run.runId });
      this.#updateMessage(assistantMessage.messageId, { mode: run.mode });

      for await (const event of run.events) {
        if (
          abortController.signal.aborted ||
          !this.#isCurrentConversation(record.conversationId)
        ) {
          throw new DOMException("Conversation scope changed", "AbortError");
        }
        if (event.type === "text_delta") {
          const current = this.#findMessage(assistantMessage.messageId);
          this.#updateMessage(assistantMessage.messageId, {
            body: `${current?.body ?? ""}${event.text}`,
          });
        } else if (event.type === "card_added") {
          const current = this.#findMessage(assistantMessage.messageId);
          this.#updateMessage(assistantMessage.messageId, {
            cards: [...(current?.cards ?? []), event.card],
          });
        }
      }

      this.#updateMessage(assistantMessage.messageId, { status: "complete" });
      const storageFailure = this.#finishRun();
      return {
        status: "completed",
        assistantMessageId: assistantMessage.messageId,
        ...(storageFailure ? { storageFailure } : {}),
      };
    } catch (error) {
      const cancelled = abortController.signal.aborted || abortError(error);
      if (!this.#isCurrentConversation(record.conversationId)) {
        return {
          status: cancelled ? "cancelled" : "failed",
          assistantMessageId: assistantMessage.messageId,
        };
      }
      const card = cancelled
        ? createCancelledCard(
            assistantMessage.messageId,
            this.#record?.executionMode ?? this.#transport.availabilityMode,
            () => this.#idFactory("card"),
          )
        : createFailureCard(
            assistantMessage.messageId,
            this.#record?.executionMode ?? this.#transport.availabilityMode,
            error,
            () => this.#idFactory("card"),
          );
      const current = this.#findMessage(assistantMessage.messageId);
      this.#updateMessage(assistantMessage.messageId, {
        status: cancelled ? "cancelled" : "failed",
        cards: [...(current?.cards ?? []), card],
      });
      const storageFailure = this.#finishRun();
      return {
        status: cancelled ? "cancelled" : "failed",
        assistantMessageId: assistantMessage.messageId,
        ...(storageFailure ? { storageFailure } : {}),
      };
    } finally {
      if (this.#activeAbortController === abortController) {
        this.#activeAbortController = null;
      }
    }
  }

  #appendMessage(message: ConversationMessage): void {
    const record = this.#record;
    if (!record) {
      return;
    }

    this.#record = {
      ...record,
      messages: [...record.messages, message],
      updatedAt: this.#clock(),
    };
    this.#persistAndNotify();
  }

  #findMessage(messageId: string): ConversationMessage | undefined {
    return this.#record?.messages.find(
      (message) => message.messageId === messageId,
    );
  }

  #isCurrentConversation(conversationId: string): boolean {
    return this.#record?.conversationId === conversationId;
  }

  #updateMessage(
    messageId: string,
    patch: Partial<ConversationMessage>,
  ): void {
    const record = this.#record;
    if (!record) {
      return;
    }

    this.#record = {
      ...record,
      messages: record.messages.map((message) =>
        message.messageId === messageId ? { ...message, ...patch } : message,
      ),
      updatedAt: this.#clock(),
    };
    this.#notify();
  }

  #updateRecord(patch: Partial<ConversationRecord>): void {
    if (!this.#record) {
      return;
    }

    this.#record = { ...this.#record, ...patch, updatedAt: this.#clock() };
    this.#notify();
  }

  #finishRun(): ConversationStorageFailure | undefined {
    this.#updateRecord({ activeRunId: null });
    const saved = this.#record ? this.#repository.save(this.#record) : null;
    return saved?.status === "failed" ? saved.error : undefined;
  }

  #persistAndNotify(): void {
    if (this.#record) {
      this.#repository.save(this.#record);
    }
    this.#notify();
  }

  #notify(): void {
    if (!this.#record) {
      return;
    }

    for (const listener of this.#listeners) {
      listener(this.#record);
    }
  }
}
