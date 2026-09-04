import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  chatOnlyHomeFixture,
  selectHomeStartup,
} from "../fixtures/chatOnlyHome.ts";
import {
  defaultConversationEditorState,
  restoreConversationEditorState,
  serializeConversationEditorState,
} from "../editors/state.ts";
import { blockedConversationAvailability } from "../editors/runtime.ts";

test("fresh launch fixture contains only the conversation editor", () => {
  assert.deepEqual(
    chatOnlyHomeFixture.areas.map((area) => area.editorId),
    ["assistant.conversation"],
  );
  assert.deepEqual(chatOnlyHomeFixture.drawers, {
    left: "hidden",
    right: "hidden",
    top: "hidden",
    bottom: "hidden",
  });
  assert.deepEqual(chatOnlyHomeFixture.edgeAffordances, [
    "left",
    "right",
    "top",
    "bottom",
  ]);
  assert.equal(chatOnlyHomeFixture.autoOpenAdditionalEditors, false);
  assert.doesNotMatch(JSON.stringify(chatOnlyHomeFixture), /dashboard|sidebar|inspector|console/i);
});

test("checked-in JSON fixture matches the typed fixture", () => {
  const fixtureUrl = new URL(
    "../fixtures/chat-only-home.fixture.json",
    import.meta.url,
  );
  const checkedIn = JSON.parse(readFileSync(fixtureUrl, "utf8"));
  assert.deepEqual(checkedIn, chatOnlyHomeFixture);
});

test("startup policy uses Home only for a truly fresh launch", () => {
  const fresh = selectHomeStartup({ judgeMode: false });
  assert.equal(fresh.status, "ready");
  if (fresh.status === "ready") {
    assert.equal(fresh.layout, chatOnlyHomeFixture);
  }

  assert.deepEqual(
    selectHomeStartup({ savedWorkspaceId: "workspace_custom", judgeMode: false }),
    { status: "delegated", reason: "saved_workspace" },
  );
  assert.deepEqual(
    selectHomeStartup({ deepLinkEditorId: "scene.viewport.3d", judgeMode: false }),
    { status: "delegated", reason: "deep_link" },
  );
  assert.deepEqual(selectHomeStartup({ judgeMode: true }), {
    status: "delegated",
    reason: "judge_mode",
  });
});

test("invalid editor-local state restores to the visible blocked default", () => {
  assert.equal(restoreConversationEditorState({ broken: true }), defaultConversationEditorState);
  assert.equal(blockedConversationAvailability.state, "blocked");
  assert.match(blockedConversationAvailability.message, /尚未连接/);
});

test("serializable editor state round-trips without runtime objects", () => {
  const serialized = serializeConversationEditorState({
    ...defaultConversationEditorState,
    composerDraft: "打开 3D 视图",
    pendingAttachments: [
      {
        attachmentId: "att_project_001",
        kind: "project",
        name: "RememberHome",
      },
    ],
  });
  assert.deepEqual(restoreConversationEditorState(serialized), serialized);
  assert.equal(JSON.stringify(serialized).includes("AbortController"), false);
});
