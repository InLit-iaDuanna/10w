import type { EditorDefinition } from "@sceneops/core-ui";
import {
  restoreConversationEditorState,
  defaultConversationEditorState,
  serializeConversationEditorState,
  type ConversationEditorState,
} from "./editors/state.ts";

export const assistantConversationEditor = {
  id: "assistant.conversation",
  title: "对话",
  icon: "message-circle",
  category: "assistant",
  load: async () => {
    await import("./editors/conversation.css");
    return import("./editors/ConversationEditor.tsx");
  },
  defaultPlacement: { mode: "tab" },
  minWidth: 320,
  minHeight: 280,
  singleton: true,
  initialState: () => structuredClone(defaultConversationEditorState),
  requiredPermissions: ["conversation:read"],
  optionalIntegrations: ["llm-provider"],
  serializeState: serializeConversationEditorState,
  restoreState: restoreConversationEditorState,
} satisfies EditorDefinition<ConversationEditorState>;
