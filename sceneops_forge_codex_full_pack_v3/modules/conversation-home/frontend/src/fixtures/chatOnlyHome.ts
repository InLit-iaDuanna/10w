export interface ChatOnlyHomeFixture {
  schemaVersion: 1;
  workspaceId: "home";
  source: "default";
  areas: Array<{
    editorId: "assistant.conversation";
    instanceId: string;
    placement: "center";
    locked: false;
  }>;
  drawers: Record<"left" | "right" | "top" | "bottom", "hidden">;
  edgeAffordances: Array<"left" | "right" | "top" | "bottom">;
  autoOpenAdditionalEditors: false;
}

export const chatOnlyHomeFixture: ChatOnlyHomeFixture = {
  schemaVersion: 1,
  workspaceId: "home",
  source: "default",
  areas: [
    {
      editorId: "assistant.conversation",
      instanceId: "editor_conversation_home",
      placement: "center",
      locked: false,
    },
  ],
  drawers: {
    left: "hidden",
    right: "hidden",
    top: "hidden",
    bottom: "hidden",
  },
  edgeAffordances: ["left", "right", "top", "bottom"],
  autoOpenAdditionalEditors: false,
};

export interface StartupContext {
  savedWorkspaceId?: string;
  deepLinkEditorId?: string;
  judgeMode: boolean;
}

export type HomeStartupDecision =
  | { status: "ready"; reason: "fresh_launch"; layout: ChatOnlyHomeFixture }
  | {
      status: "delegated";
      reason: "saved_workspace" | "deep_link" | "judge_mode";
    };

export function selectHomeStartup(
  context: StartupContext,
): HomeStartupDecision {
  if (context.savedWorkspaceId) {
    return { status: "delegated", reason: "saved_workspace" };
  }

  if (context.deepLinkEditorId) {
    return { status: "delegated", reason: "deep_link" };
  }

  if (context.judgeMode) {
    return { status: "delegated", reason: "judge_mode" };
  }

  return {
    status: "ready",
    reason: "fresh_launch",
    layout: chatOnlyHomeFixture,
  };
}
