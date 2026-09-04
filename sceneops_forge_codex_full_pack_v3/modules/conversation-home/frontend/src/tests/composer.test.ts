import assert from "node:assert/strict";
import test from "node:test";
import { toConversationAttachment } from "../composer/attachments.ts";
import {
  handoffComposerSearch,
  resolveComposerKeyboardIntent,
} from "../composer/keyboard.ts";
import { buildContextChips } from "../components/contextChips.ts";
import { presentExecutionMode } from "../contracts/executionMode.ts";
import { getConversationCardAction } from "../conversation/cards.ts";

function keyInput(overrides: Partial<Parameters<typeof resolveComposerKeyboardIntent>[0]>) {
  return {
    key: "x",
    value: "",
    shiftKey: false,
    controlKey: false,
    metaKey: false,
    isComposing: false,
    isStreaming: false,
    ...overrides,
  };
}

test("accessible composer keyboard flow covers send, newline, cancel, and search", () => {
  assert.equal(
    resolveComposerKeyboardIntent(keyInput({ key: "Enter", value: "hello" })),
    "send",
  );
  assert.equal(
    resolveComposerKeyboardIntent(
      keyInput({ key: "Enter", value: "hello", shiftKey: true }),
    ),
    "newline",
  );
  assert.equal(
    resolveComposerKeyboardIntent(keyInput({ key: "Escape", isStreaming: true })),
    "cancel_stream",
  );
  assert.equal(
    resolveComposerKeyboardIntent(keyInput({ key: "k", controlKey: true })),
    "open_command_search",
  );
  assert.equal(
    resolveComposerKeyboardIntent(keyInput({ key: "K", metaKey: true })),
    "open_command_search",
  );
  assert.equal(
    resolveComposerKeyboardIntent(keyInput({ key: "/", value: "" })),
    "open_slash_commands",
  );
  assert.equal(
    resolveComposerKeyboardIntent(
      keyInput({ key: "Enter", value: "中文", isComposing: true }),
    ),
    "none",
    "IME composition must not accidentally send",
  );
});

test("slash and command search hand off to one existing command definition", async () => {
  const calls: Array<{ commandId: string; input: unknown }> = [];
  const commands = {
    async execute(commandId: "workbench.command_search.open", input: unknown) {
      calls.push({ commandId, input });
      return null;
    },
  };
  await handoffComposerSearch(commands, "open_command_search");
  await handoffComposerSearch(commands, "open_slash_commands");

  assert.deepEqual(calls, [
    {
      commandId: "workbench.command_search.open",
      input: { mode: "all", initialQuery: "" },
    },
    {
      commandId: "workbench.command_search.open",
      input: { mode: "slash", initialQuery: "/" },
    },
  ]);
});

test("file and project drops produce inert attachment metadata", () => {
  let nextId = 0;
  const createId = () => `att_${++nextId}`;
  const file = toConversationAttachment(
    {
      name: "door.glb",
      mediaType: "model/gltf-binary",
      sizeBytes: 128,
      isDirectory: false,
    },
    createId,
  );
  const project = toConversationAttachment(
    {
      name: "Assets",
      sizeBytes: 0,
      isDirectory: true,
    },
    createId,
  );
  assert.deepEqual(file, {
    attachmentId: "att_1",
    kind: "file",
    name: "door.glb",
    mediaType: "model/gltf-binary",
    sizeBytes: 128,
  });
  assert.equal(project.kind, "project");
  assert.equal("path" in project, false, "raw local paths are not persisted");
});

test("Live, Cached, Mock, Planned, and Blocked have explicit text labels", () => {
  assert.deepEqual(
    ["live", "cached", "mock", "planned", "blocked"].map((mode) =>
      presentExecutionMode(mode as Parameters<typeof presentExecutionMode>[0]).label,
    ),
    ["LIVE", "CACHED", "MOCK", "PLANNED", "BLOCKED"],
  );
});

test("context chips expose project, scene, selection, feature, build, and issue", () => {
  const chips = buildContextChips({
    projectId: "prj_home",
    projectName: "Find My Way Home",
    sceneId: "scn_hallway",
    sceneName: "Home Hallway",
    selectedSceneObjectIds: ["obj_door_01"],
    activeFeatureId: "feature_key_door",
    activeBuildId: "build_001",
    activeIssueId: "issue_visibility",
  });
  assert.deepEqual(
    chips.map((chip) => chip.label),
    ["项目", "场景", "对象", "功能", "构建", "问题"],
  );
});

test("action lookup works for artifact, approval, and open-in-tool cards", () => {
  const action = {
    actionId: "act_artifact_open_001",
    type: "artifact.open",
    title: "打开产物",
    input: { artifactId: "artifact_001" },
  } as const;
  assert.equal(
    getConversationCardAction({
      cardId: "card_artifact_001",
      kind: "artifact",
      mode: "cached",
      title: "构建",
      artifactType: "unity-build",
      provenance: {
        artifactId: "artifact_001",
        producingModule: "build-release",
        executionMode: "cached",
        createdAt: "2026-09-04T00:00:00Z",
        approvalState: "approved",
      },
      openAction: action,
    })?.actionId,
    action.actionId,
  );
  assert.equal(
    getConversationCardAction({
      cardId: "card_open_001",
      kind: "open_in_tool",
      mode: "planned",
      title: "打开工具",
      description: "查看产物",
      action,
    })?.type,
    "artifact.open",
  );
  assert.equal(
    getConversationCardAction({
      cardId: "card_approval_001",
      kind: "approval",
      mode: "planned",
      approvalId: "approval_001",
      changeSetId: "changeset_001",
      title: "请求批准",
      risk: "high",
      state: "waiting",
      requestAction: {
        actionId: "act_approval_request_001",
        type: "changeset.approval.request",
        title: "请求批准",
        input: { changeSetId: "changeset_001" },
      },
    })?.type,
    "changeset.approval.request",
  );
});
