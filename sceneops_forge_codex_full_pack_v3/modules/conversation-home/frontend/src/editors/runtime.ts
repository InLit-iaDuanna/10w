import type {
  ActionExecutionResult,
  PreparedAction,
} from "../assistant-actions/coordinator.ts";
import type { AssistantAction } from "../assistant-actions/types.ts";
import type { SuggestedCommand } from "../conversation/cards.ts";
import type { ConversationOperationResult } from "../conversation/controller.ts";
import type { BrowserAttachmentSource } from "../composer/attachments.ts";
import type { ExecutionMode } from "../contracts/executionMode.ts";
import type {
  ConversationAttachment,
  ConversationRecord,
  WorkbenchContextSummary,
} from "../conversation/types.ts";

export interface ConversationAvailability {
  state: "connected" | "disconnected" | "blocked";
  mode: ExecutionMode;
  message: string;
}

export const blockedConversationAvailability: ConversationAvailability = {
  state: "blocked",
  mode: "blocked",
  message: "对话服务尚未连接 typed LLM adapter。",
};

export interface ConversationEditorRuntime {
  getSnapshot(): ConversationRecord | null;
  subscribe(listener: (record: ConversationRecord) => void): () => void;
  getAvailability(): ConversationAvailability;
  getContextSummary(): WorkbenchContextSummary;
  stageAttachments(
    sources: BrowserAttachmentSource[],
  ): Promise<ConversationAttachment[]>;
  send(
    text: string,
    attachments: ConversationAttachment[],
  ): Promise<ConversationOperationResult>;
  cancelStream(): void;
  retry(assistantMessageId: string): Promise<ConversationOperationResult>;
  openCommandSearch(mode: "all" | "slash"): Promise<void>;
  prepareAssistantAction(action: AssistantAction): Promise<PreparedAction>;
  executeAssistantAction(
    actionId: string,
    confirmLayout: boolean,
  ): Promise<ActionExecutionResult>;
  cancelAssistantAction(actionId: string): void;
  executeSuggestedCommand(command: SuggestedCommand): Promise<void>;
}
