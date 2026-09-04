import type { AssistantAction } from "../assistant-actions/types.ts";
import type { ExecutionMode } from "../contracts/executionMode.ts";
import type { JsonObject } from "../contracts/json.ts";

interface ConversationCardBase<TKind extends string> {
  cardId: string;
  kind: TKind;
  mode: ExecutionMode;
}

export type ProgressNodeState =
  | "queued"
  | "running"
  | "waiting_approval"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "blocked";

export interface ProgressNode {
  nodeId: string;
  label: string;
  state: ProgressNodeState;
  detail?: string;
}

export type ProgressCard = ConversationCardBase<"progress"> & {
  title: string;
  runId: string;
  nodes: ProgressNode[];
};

export interface ArtifactProvenanceSummary {
  artifactId: string;
  producingModule: string;
  executionMode: ExecutionMode;
  createdAt: string;
  approvalState: string;
  tool?: string;
  adapterVersion?: string;
}

export type ArtifactCard = ConversationCardBase<"artifact"> & {
  title: string;
  artifactType: string;
  previewUrl?: string;
  provenance: ArtifactProvenanceSummary;
  openAction?: AssistantAction;
};

export interface SuggestedCommand {
  commandId: string;
  title: string;
  input: JsonObject;
}

export type ErrorCard = ConversationCardBase<"error"> & {
  code: string;
  message: string;
  requestId?: string;
  retryable: boolean;
  missingPermissions: string[];
  missingIntegrations: string[];
  suggestedActions: SuggestedCommand[];
};

export type ApprovalCard = ConversationCardBase<"approval"> & {
  approvalId: string;
  changeSetId: string;
  title: string;
  risk: "low" | "medium" | "high" | "critical";
  state: "requested" | "waiting" | "approved" | "rejected" | "expired";
  requestAction?: AssistantAction;
};

export type OpenInToolCard = ConversationCardBase<"open_in_tool"> & {
  title: string;
  description: string;
  action: AssistantAction;
};

export type AssistantActionCard = ConversationCardBase<"assistant_action"> & {
  title: string;
  description?: string;
  action: AssistantAction;
};

export type ConversationCard =
  | ProgressCard
  | ArtifactCard
  | ErrorCard
  | ApprovalCard
  | OpenInToolCard
  | AssistantActionCard;

export function getConversationCardAction(
  card: ConversationCard,
): AssistantAction | undefined {
  if (card.kind === "artifact") {
    return card.openAction;
  }
  if (card.kind === "approval") {
    return card.requestAction;
  }
  if (card.kind === "open_in_tool" || card.kind === "assistant_action") {
    return card.action;
  }
  return undefined;
}
