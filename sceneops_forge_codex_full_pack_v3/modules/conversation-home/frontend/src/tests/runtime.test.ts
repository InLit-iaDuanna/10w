import assert from "node:assert/strict";
import test from "node:test";
import type {
  CommandAvailability,
  CommandRequest,
  LayoutActionPreview,
  WorkbenchCommandBusPort,
  WorkbenchContextSnapshot,
} from "../assistant-actions/coordinator.ts";
import { toConversationAttachment } from "../composer/attachments.ts";
import { ConversationController } from "../conversation/controller.ts";
import { ConversationRepository } from "../conversation/repository.ts";
import type { JsonValue } from "../contracts/json.ts";
import {
  createConversationEditorRuntime,
  WorkbenchCommandUnavailableError,
} from "../editors/createRuntime.ts";
import { MemoryStorage } from "../fixtures/MemoryStorage.ts";
import {
  openSceneViewScript,
  ScriptedConversationTransport,
} from "../fixtures/ScriptedConversationTransport.ts";

const context: WorkbenchContextSnapshot = {
  projectId: "prj_home",
  branchId: null,
  sceneId: null,
  selectedSceneObjectIds: [],
  selectedAssetIds: [],
  activeFeatureId: null,
  activeTaskId: null,
  activeChangeSetId: null,
  activeRenderJobId: null,
  activeBuildId: null,
  activePlaytestRunId: null,
  activeIssueId: null,
};

function available(): CommandAvailability {
  return {
    state: "available",
    layoutEffect: "none",
    missingPermissions: [],
    missingIntegrations: [],
    suggestedActions: [],
    approval: { required: false, state: "not_required" },
  };
}

class RuntimeBus implements WorkbenchCommandBusPort {
  availability = available();
  readonly executed: CommandRequest[] = [];

  async inspect(): Promise<CommandAvailability> {
    return this.availability;
  }

  async preview(): Promise<LayoutActionPreview> {
    return {
      mode: "planned",
      summary: "预览",
      changes: [],
      targetDescription: "当前区域",
    };
  }

  async execute<TResult extends JsonValue = JsonValue>(
    request: CommandRequest,
  ): Promise<TResult> {
    this.executed.push(request);
    return null as TResult;
  }
}

function createRuntime(bus: RuntimeBus) {
  let id = 0;
  let attachmentId = 0;
  const controller = new ConversationController(
    new ConversationRepository(new MemoryStorage(), new MemoryStorage()),
    new ScriptedConversationTransport([openSceneViewScript]),
    (kind) => `${kind === "conversation" ? "cnv" : kind === "message" ? "msg" : "card"}_runtime_${++id}`,
    () => "2026-09-04T00:00:00.000Z",
  );
  controller.initialize({ kind: "project", projectId: "prj_home" });
  return createConversationEditorRuntime({
    controller,
    commandBus: bus,
    getWorkbenchContext: () => context,
    getContextSummary: () => ({
      projectId: "prj_home",
      sceneId: null,
      selectedSceneObjectIds: [],
      activeFeatureId: null,
      activeBuildId: null,
      activeIssueId: null,
    }),
    getConversationAvailability: () => ({
      state: "connected",
      mode: "mock",
      message: "确定性 Mock 已连接。",
    }),
    attachmentStager: {
      stage: async (sources) =>
        sources.map((source) =>
          toConversationAttachment(
            source.entry,
            () => `att_runtime_${++attachmentId}`,
          ),
        ),
    },
  });
}

test("editor runtime exposes controller updates and command-search on the shared bus", async () => {
  const bus = new RuntimeBus();
  const runtime = createRuntime(bus);
  const snapshots: number[] = [];
  const unsubscribe = runtime.subscribe((record) => snapshots.push(record.messages.length));

  const result = await runtime.send("在右侧打开 3D 视图", []);
  assert.equal(result.status, "completed");
  assert.equal(runtime.getSnapshot()?.messages.length, 2);
  assert.equal(snapshots.at(-1), 2);
  unsubscribe();

  await runtime.openCommandSearch("slash");
  assert.deepEqual(bus.executed.at(-1), {
    commandId: "workbench.command_search.open",
    input: { mode: "slash", initialQuery: "/" },
    source: { surface: "command_search" },
  });
});

test("suggested commands still enforce command-bus availability and approval", async () => {
  const bus = new RuntimeBus();
  const runtime = createRuntime(bus);
  bus.availability = {
    state: "unavailable",
    layoutEffect: "none",
    code: "PERMISSION_DENIED",
    message: "没有权限。",
    missingPermissions: ["integration:read"],
    missingIntegrations: [],
    suggestedActions: [],
    approval: { required: false, state: "not_required" },
  };

  await assert.rejects(
    runtime.executeSuggestedCommand({
      commandId: "integration.open",
      title: "打开集成中心",
      input: { integrationId: "unity" },
    }),
    (error: unknown) =>
      error instanceof WorkbenchCommandUnavailableError &&
      error.availability.missingPermissions[0] === "integration:read",
  );
  assert.equal(bus.executed.length, 0);
});

test("attachment sources cross the typed stager before entering editor state", async () => {
  const runtime = createRuntime(new RuntimeBus());
  const file = new File(["scene"], "scene.unity", { type: "text/plain" });

  const attachments = await runtime.stageAttachments([
    {
      entry: {
        name: file.name,
        mediaType: file.type,
        sizeBytes: file.size,
        isDirectory: false,
      },
      file,
    },
  ]);

  assert.deepEqual(attachments, [
    {
      attachmentId: "att_runtime_1",
      kind: "file",
      name: "scene.unity",
      mediaType: "text/plain",
      sizeBytes: 5,
    },
  ]);
});
