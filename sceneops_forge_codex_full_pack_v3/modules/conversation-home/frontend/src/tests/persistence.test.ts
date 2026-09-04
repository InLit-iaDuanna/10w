import assert from "node:assert/strict";
import test from "node:test";
import {
  ConversationRepository,
  createConversationRecord,
  type KeyValueStorage,
} from "../conversation/repository.ts";
import { MemoryStorage } from "../fixtures/MemoryStorage.ts";

const now = "2026-09-04T00:00:00.000Z";

test("project and pre-project conversations use separate storage lifetimes", () => {
  const persistent = new MemoryStorage();
  const temporary = new MemoryStorage();
  const repository = new ConversationRepository(persistent, temporary);
  const projectRecord = createConversationRecord(
    { kind: "project", projectId: "prj_remember_home" },
    "cnv_project_001",
    "live",
    now,
  );
  const temporaryRecord = createConversationRecord(
    { kind: "pre_project", sessionId: "session_001" },
    "cnv_temporary_001",
    "mock",
    now,
  );

  assert.deepEqual(repository.save(projectRecord), { status: "saved" });
  assert.deepEqual(repository.save(temporaryRecord), { status: "saved" });
  assert.equal(persistent.entries().length, 1);
  assert.equal(temporary.entries().length, 1);
  assert.match(persistent.entries()[0]?.[0] ?? "", /:project:/);
  assert.match(temporary.entries()[0]?.[0] ?? "", /:pre_project:/);

  const nextRepository = new ConversationRepository(persistent, temporary);
  assert.deepEqual(
    nextRepository.load({ kind: "project", projectId: "prj_remember_home" }),
    { status: "loaded", record: projectRecord },
  );
  assert.deepEqual(
    nextRepository.load({ kind: "pre_project", sessionId: "session_001" }),
    { status: "loaded", record: temporaryRecord },
  );
});

test("a different project cannot read another project's conversation", () => {
  const persistent = new MemoryStorage();
  const repository = new ConversationRepository(persistent, new MemoryStorage());
  repository.save(
    createConversationRecord(
      { kind: "project", projectId: "prj_alpha" },
      "cnv_alpha_001",
      "cached",
      now,
    ),
  );

  assert.deepEqual(
    repository.load({ kind: "project", projectId: "prj_beta" }),
    { status: "missing" },
  );
});

test("malformed or scope-mismatched data returns a visible schema failure", () => {
  const persistent = new MemoryStorage();
  const temporary = new MemoryStorage();
  const repository = new ConversationRepository(persistent, temporary);
  const scope = { kind: "project", projectId: "prj_home" } as const;

  repository.save(createConversationRecord(scope, "cnv_home_001", "mock", now));
  const [key] = persistent.entries()[0] ?? [];
  assert.ok(key);
  persistent.setItem(key, "{not json");
  const malformed = repository.load(scope);
  assert.equal(malformed.status, "failed");
  if (malformed.status === "failed") {
    assert.equal(malformed.error.code, "CONVERSATION_STORAGE_INVALID");
  }

  const wrongScope = createConversationRecord(
    { kind: "project", projectId: "prj_other" },
    "cnv_other_001",
    "mock",
    now,
  );
  persistent.setItem(key, JSON.stringify(wrongScope));
  const mismatched = repository.load(scope);
  assert.equal(mismatched.status, "failed");
  if (mismatched.status === "failed") {
    assert.equal(mismatched.error.code, "CONVERSATION_STORAGE_INVALID");
  }
});

test("storage write failures are reported instead of silently discarded", () => {
  const unavailableStorage: KeyValueStorage = {
    getItem: () => null,
    setItem: () => {
      throw new Error("quota denied");
    },
    removeItem: () => undefined,
  };
  const repository = new ConversationRepository(
    unavailableStorage,
    new MemoryStorage(),
  );
  const result = repository.save(
    createConversationRecord(
      { kind: "project", projectId: "prj_home" },
      "cnv_home_001",
      "blocked",
      now,
    ),
  );

  assert.equal(result.status, "failed");
  if (result.status === "failed") {
    assert.equal(result.error.code, "CONVERSATION_STORAGE_UNAVAILABLE");
    assert.match(result.error.message, /quota denied/);
  }
});
