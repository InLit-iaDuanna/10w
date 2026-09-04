import {
  ConversationTransportError,
  type ConversationRequest,
  type ConversationRun,
  type ConversationStreamEvent,
  type ConversationTransport,
} from "../conversation/transport.ts";

export interface ConversationScript {
  prompt: string;
  runId: string;
  events: ConversationStreamEvent[];
}

export class ScriptedConversationTransport implements ConversationTransport {
  readonly availabilityMode = "mock" as const;
  readonly #scripts: Map<string, ConversationScript>;

  constructor(scripts: ConversationScript[]) {
    this.#scripts = new Map(scripts.map((script) => [script.prompt, script]));
  }

  async start(
    request: ConversationRequest,
    signal: AbortSignal,
  ): Promise<ConversationRun> {
    const script = this.#scripts.get(request.userMessage.body);
    if (!script) {
      throw new ConversationTransportError({
        code: "MOCK_SCRIPT_NOT_FOUND",
        message: "确定性 Mock 中没有匹配的对话脚本。",
        retryable: false,
        missingPermissions: [],
        missingIntegrations: [],
        suggestedActions: [],
      });
    }

    return {
      runId: script.runId,
      mode: "mock",
      events: scriptedEvents(script.events, signal),
    };
  }
}

async function* scriptedEvents(
  events: ConversationStreamEvent[],
  signal: AbortSignal,
): AsyncIterable<ConversationStreamEvent> {
  for (const event of events) {
    if (signal.aborted) {
      throw new DOMException("Conversation cancelled", "AbortError");
    }
    await Promise.resolve();
    yield event;
  }
}

export const openSceneViewScript: ConversationScript = {
  prompt: "在右侧打开 3D 视图",
  runId: "run_mock_open_scene_001",
  events: [
    {
      type: "text_delta",
      text: "我可以在右侧拆分 3D 视图。请先预览并确认布局。",
    },
    {
      type: "card_added",
      card: {
        cardId: "card_mock_open_scene_001",
        kind: "assistant_action",
        mode: "mock",
        title: "打开工具",
        action: {
          actionId: "act_open_scene_right_001",
          type: "workbench.open_editor",
          title: "在右侧打开 3D 视图",
          requiresConfirmation: true,
          input: {
            editorId: "scene.viewport.3d",
            placement: {
              mode: "split",
              direction: "right",
              relativeToInstanceId: "editor_conversation_home",
            },
          },
        },
      },
    },
    { type: "completed" },
  ],
};
