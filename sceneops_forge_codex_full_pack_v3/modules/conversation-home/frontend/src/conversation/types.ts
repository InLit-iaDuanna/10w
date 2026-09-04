import type { ExecutionMode } from "../contracts/executionMode.ts";
import type { ConversationCard } from "./cards.ts";

export type ConversationScope =
  | { kind: "project"; projectId: string }
  | { kind: "pre_project"; sessionId: string };

export type ConversationMessageStatus =
  | "complete"
  | "streaming"
  | "failed"
  | "cancelled";

export type ConversationAttachment = {
  attachmentId: string;
  kind: "file" | "project";
  name: string;
  mediaType?: string;
  sizeBytes?: number;
};

export interface ConversationMessage {
  messageId: string;
  role: "user" | "assistant" | "system";
  body: string;
  createdAt: string;
  mode: ExecutionMode;
  status: ConversationMessageStatus;
  replyToMessageId?: string;
  attachments: ConversationAttachment[];
  cards: ConversationCard[];
}

export interface ConversationRecord {
  schemaVersion: 1;
  conversationId: string;
  scope: ConversationScope;
  messages: ConversationMessage[];
  executionMode: ExecutionMode;
  updatedAt: string;
  activeRunId?: string | null;
}

export interface WorkbenchContextSummary {
  projectId: string | null;
  projectName?: string;
  sceneId: string | null;
  sceneName?: string;
  selectedSceneObjectIds: string[];
  activeFeatureId: string | null;
  activeBuildId: string | null;
  activeIssueId: string | null;
}
