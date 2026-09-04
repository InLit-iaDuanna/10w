import assert from "node:assert/strict";
import test from "node:test";
import { ConversationController, type IdFactory } from "../conversation/controller.ts";
import { ConversationRepository } from "../conversation/repository.ts";
import type {
  ConversationRequest,
  ConversationRun,
  ConversationStreamEvent,
  ConversationTransport,
} from "../conversation/transport.ts";
import { MemoryStorage } from "../fixtures/MemoryStorage.ts";
import {
  openSceneViewScript,
  ScriptedConversationTransport,
} from "../fixtures/ScriptedConversationTransport.ts";

function sequentialIds(): IdFactory {
  const counts = { conversation: 0, message: 0, card: 0 };
  return (kind) => {
    counts[kind] += 1;
    const prefixes = { conversation: "cnv", message: "msg", card: "card" };
    return `${prefixes[kind]}_test_${String(counts[kind]).padStart(3, "0")}`;
  };
}

const fixedClock = () => "2026-09-04T00:00:00.000Z";

function createController(transport: ConversationTransport) {
  const persistent = new MemoryStorage();
  const temporary = new MemoryStorage();
  const repository = new ConversationRepository(persistent, temporary);
  const controller = new ConversationController(
    repository,
    transport,
    sequentialIds(),
    fixedClock,
  );
  return { controller, repository, persistent, temporary };
}

test("deterministic mock stream records text, action card, and explicit mode", async () => {
  const transport = new ScriptedConversationTransport([openSceneViewScript]);
  const { controller, repository } = createController(transport);
  const initialized = controller.initialize({
    kind: "project",
    projectId: "prj_remember_home",
  });
  assert.equal(initialized.status, "ready");

  const result = await controller.send("在右侧打开 3D 视图");
  assert.equal(result.status, "completed");
  const record = controller.snapshot;
  assert.ok(record);
  assert.equal(record.executionMode, "mock");
  assert.equal(record.activeRunId, null);
  assert.equal(record.messages.length, 2);
  assert.equal(record.messages[0]?.role, "user");
  assert.equal(record.messages[1]?.status, "complete");
  assert.match(record.messages[1]?.body ?? "", /预览并确认布局/);
  assert.equal(record.messages[1]?.cards[0]?.kind, "assistant_action");
  assert.equal(record.messages[1]?.cards[0]?.mode, "mock");

  const reloaded = repository.load({
    kind: "project",
    projectId: "prj_remember_home",
  });
  assert.equal(reloaded.status, "loaded");
  if (reloaded.status === "loaded") {
    assert.deepEqual(reloaded.record, record);
  }
});

test("missing mock script produces a visible structured failure", async () => {
  const { controller } = createController(new ScriptedConversationTransport([]));
  controller.initialize({ kind: "pre_project", sessionId: "session_failure" });
  const result = await controller.send("未知脚本");

  assert.equal(result.status, "failed");
  const assistant = controller.snapshot?.messages.at(-1);
  assert.equal(assistant?.status, "failed");
  assert.equal(assistant?.cards[0]?.kind, "error");
  if (assistant?.cards[0]?.kind === "error") {
    assert.equal(assistant.cards[0].code, "MOCK_SCRIPT_NOT_FOUND");
    assert.equal(assistant.cards[0].mode, "mock");
  }
});

class CancelThenSuccessTransport implements ConversationTransport {
  readonly availabilityMode = "mock" as const;
  readonly blocked: Promise<void>;
  #releaseBlocked!: () => void;
  #attempt = 0;

  constructor() {
    this.blocked = new Promise((resolve) => {
      this.#releaseBlocked = resolve;
    });
  }

  async start(
    _request: ConversationRequest,
    signal: AbortSignal,
  ): Promise<ConversationRun> {
    this.#attempt += 1;
    return {
      runId: `run_mock_attempt_${this.#attempt}`,
      mode: "mock",
      events: this.#attempt === 1
        ? this.#cancelledEvents(signal)
        : this.#successfulEvents(),
    };
  }

  async *#cancelledEvents(
    signal: AbortSignal,
  ): AsyncIterable<ConversationStreamEvent> {
    yield { type: "text_delta", text: "生成中" };
    this.#releaseBlocked();
    await new Promise<void>((_resolve, reject) => {
      signal.addEventListener(
        "abort",
        () => reject(new DOMException("cancelled", "AbortError")),
        { once: true },
      );
    });
  }

  async *#successfulEvents(): AsyncIterable<ConversationStreamEvent> {
    yield { type: "text_delta", text: "重试成功" };
    yield { type: "completed" };
  }
}

test("stream cancel remains retryable and retry does not duplicate the user message", async () => {
  const transport = new CancelThenSuccessTransport();
  const { controller } = createController(transport);
  controller.initialize({ kind: "pre_project", sessionId: "session_cancel" });

  const pending = controller.send("请生成回复");
  await transport.blocked;
  assert.equal(controller.cancel(), true);
  const cancelled = await pending;
  assert.equal(cancelled.status, "cancelled");

  const cancelledReply = controller.snapshot?.messages.at(-1);
  assert.equal(cancelledReply?.status, "cancelled");
  if (cancelledReply?.cards[0]?.kind === "error") {
    assert.equal(cancelledReply.cards[0].code, "STREAM_CANCELLED");
    assert.equal(cancelledReply.cards[0].retryable, true);
  }

  const retried = await controller.retry(cancelledReply?.messageId ?? "");
  assert.equal(retried.status, "completed");
  const messages = controller.snapshot?.messages ?? [];
  assert.equal(messages.filter((message) => message.role === "user").length, 1);
  assert.equal(messages.filter((message) => message.role === "assistant").length, 2);
  assert.equal(messages.at(-1)?.body, "重试成功");
  assert.equal(messages.at(-1)?.status, "complete");
});

test("concurrent sends are rejected until the current stream is cancelled", async () => {
  const transport = new CancelThenSuccessTransport();
  const { controller } = createController(transport);
  controller.initialize({ kind: "pre_project", sessionId: "session_concurrent" });
  const pending = controller.send("第一条");
  await transport.blocked;

  const second = await controller.send("第二条");
  assert.deepEqual(second, {
    status: "rejected",
    code: "STREAM_ALREADY_RUNNING",
    message: "已有响应正在生成，请先取消。",
  });
  controller.cancel();
  await pending;
});

test("a failed scope load clears the previous project's record", () => {
  const transport = new ScriptedConversationTransport([openSceneViewScript]);
  const { controller, persistent } = createController(transport);
  controller.initialize({ kind: "project", projectId: "prj_alpha" });
  assert.equal(controller.snapshot?.scope.kind, "project");

  persistent.setItem(
    "sceneops:conversation-home:v1:project:prj_corrupt",
    "{broken",
  );
  const failed = controller.initialize({
    kind: "project",
    projectId: "prj_corrupt",
  });
  assert.equal(failed.status, "failed");
  assert.equal(controller.snapshot, null);
});

test("switching scope cancels an old stream without mutating the new conversation", async () => {
  const transport = new CancelThenSuccessTransport();
  const { controller } = createController(transport);
  controller.initialize({ kind: "pre_project", sessionId: "session_old" });
  const oldRun = controller.send("旧会话请求");
  await transport.blocked;

  const next = controller.initialize({
    kind: "project",
    projectId: "prj_new",
  });
  assert.equal(next.status, "ready");
  const oldResult = await oldRun;
  assert.equal(oldResult.status, "cancelled");
  assert.deepEqual(controller.snapshot?.scope, {
    kind: "project",
    projectId: "prj_new",
  });
  assert.equal(controller.snapshot?.messages.length, 0);
  assert.equal(controller.snapshot?.activeRunId, null);
});

test("a persisted in-progress response recovers as visible retryable interruption", () => {
  const repository = new ConversationRepository(
    new MemoryStorage(),
    new MemoryStorage(),
  );
  repository.save({
    schemaVersion: 1,
    conversationId: "cnv_interrupted_001",
    scope: { kind: "project", projectId: "prj_interrupted" },
    executionMode: "live",
    updatedAt: "2026-09-04T00:00:00.000Z",
    activeRunId: "run_interrupted_001",
    messages: [
      {
        messageId: "msg_user_interrupted",
        role: "user",
        body: "继续构建",
        createdAt: "2026-09-04T00:00:00.000Z",
        mode: "live",
        status: "complete",
        attachments: [],
        cards: [],
      },
      {
        messageId: "msg_assistant_interrupted",
        role: "assistant",
        body: "正在检查",
        createdAt: "2026-09-04T00:00:00.000Z",
        mode: "live",
        status: "streaming",
        replyToMessageId: "msg_user_interrupted",
        attachments: [],
        cards: [],
      },
    ],
  });
  const controller = new ConversationController(
    repository,
    new ScriptedConversationTransport([openSceneViewScript]),
    sequentialIds(),
    fixedClock,
  );
  const initialized = controller.initialize({
    kind: "project",
    projectId: "prj_interrupted",
  });
  assert.equal(initialized.status, "ready");
  const reply = controller.snapshot?.messages.at(-1);
  assert.equal(reply?.status, "cancelled");
  assert.equal(controller.snapshot?.activeRunId, null);
  if (reply?.cards[0]?.kind === "error") {
    assert.equal(reply.cards[0].code, "STREAM_INTERRUPTED");
    assert.equal(reply.cards[0].retryable, true);
  } else {
    assert.fail("expected a visible interruption error card");
  }
});
