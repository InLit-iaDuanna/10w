import { validateAssistantAction } from "../assistant-actions/validate.ts";
import { isExecutionMode } from "../contracts/executionMode.ts";
import { isJsonValue } from "../contracts/json.ts";
import type {
  ConversationAttachment,
  ConversationMessage,
  ConversationRecord,
  ConversationScope,
} from "./types.ts";

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function hasOnlyKeys(value: UnknownRecord, allowed: readonly string[]): boolean {
  return Object.keys(value).every((key) => allowed.includes(key));
}

function isUtcTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.endsWith("Z") &&
    !Number.isNaN(Date.parse(value))
  );
}

function isStringArray(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.every((item) => typeof item === "string" && item.length > 0)
  );
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function isScope(value: unknown): value is ConversationScope {
  if (!isRecord(value)) {
    return false;
  }
  if (value.kind === "project") {
    return (
      hasOnlyKeys(value, ["kind", "projectId"]) &&
      typeof value.projectId === "string" &&
      value.projectId.length >= 3
    );
  }
  return (
    value.kind === "pre_project" &&
    hasOnlyKeys(value, ["kind", "sessionId"]) &&
    typeof value.sessionId === "string" &&
    value.sessionId.length >= 3
  );
}

function isAttachment(value: unknown): value is ConversationAttachment {
  return (
    isRecord(value) &&
    hasOnlyKeys(value, ["attachmentId", "kind", "name", "mediaType", "sizeBytes"]) &&
    typeof value.attachmentId === "string" &&
    /^att_[A-Za-z0-9_-]+$/.test(value.attachmentId) &&
    (value.kind === "file" || value.kind === "project") &&
    isNonEmptyString(value.name) &&
    (value.mediaType === undefined || typeof value.mediaType === "string") &&
    (value.sizeBytes === undefined ||
      (Number.isInteger(value.sizeBytes) && Number(value.sizeBytes) >= 0))
  );
}

function hasCardBase(value: UnknownRecord, kind: string): boolean {
  return (
    value.kind === kind &&
    typeof value.cardId === "string" &&
    /^card_[A-Za-z0-9_-]+$/.test(value.cardId) &&
    isExecutionMode(value.mode)
  );
}

function isSuggestedCommand(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasOnlyKeys(value, ["commandId", "title", "input"]) &&
    isNonEmptyString(value.commandId) &&
    isNonEmptyString(value.title) &&
    isRecord(value.input) &&
    isJsonValue(value.input)
  );
}

function isProgressCard(value: UnknownRecord): boolean {
  const states = [
    "queued",
    "running",
    "waiting_approval",
    "succeeded",
    "failed",
    "cancelled",
    "blocked",
  ];
  return (
    hasCardBase(value, "progress") &&
    hasOnlyKeys(value, ["cardId", "kind", "mode", "title", "runId", "nodes"]) &&
    isNonEmptyString(value.title) &&
    typeof value.runId === "string" &&
    /^run_[A-Za-z0-9_-]+$/.test(value.runId) &&
    Array.isArray(value.nodes) &&
    value.nodes.every(
      (node) =>
        isRecord(node) &&
        hasOnlyKeys(node, ["nodeId", "label", "state", "detail"]) &&
        isNonEmptyString(node.nodeId) &&
        isNonEmptyString(node.label) &&
        states.includes(String(node.state)) &&
        (node.detail === undefined || typeof node.detail === "string"),
    )
  );
}

function isProvenance(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasOnlyKeys(value, [
      "artifactId",
      "producingModule",
      "executionMode",
      "createdAt",
      "approvalState",
      "tool",
      "adapterVersion",
    ]) &&
    typeof value.artifactId === "string" &&
    value.artifactId.length >= 3 &&
    isNonEmptyString(value.producingModule) &&
    isExecutionMode(value.executionMode) &&
    isUtcTimestamp(value.createdAt) &&
    isNonEmptyString(value.approvalState) &&
    (value.tool === undefined || typeof value.tool === "string") &&
    (value.adapterVersion === undefined || typeof value.adapterVersion === "string")
  );
}

function isArtifactCard(value: UnknownRecord): boolean {
  return (
    hasCardBase(value, "artifact") &&
    hasOnlyKeys(value, [
      "cardId",
      "kind",
      "mode",
      "title",
      "artifactType",
      "previewUrl",
      "provenance",
      "openAction",
    ]) &&
    isNonEmptyString(value.title) &&
    isNonEmptyString(value.artifactType) &&
    (value.previewUrl === undefined || typeof value.previewUrl === "string") &&
    isProvenance(value.provenance) &&
    (value.openAction === undefined || validateAssistantAction(value.openAction).ok)
  );
}

function isErrorCard(value: UnknownRecord): boolean {
  return (
    hasCardBase(value, "error") &&
    hasOnlyKeys(value, [
      "cardId",
      "kind",
      "mode",
      "code",
      "message",
      "requestId",
      "retryable",
      "missingPermissions",
      "missingIntegrations",
      "suggestedActions",
    ]) &&
    isNonEmptyString(value.code) &&
    isNonEmptyString(value.message) &&
    (value.requestId === undefined || typeof value.requestId === "string") &&
    typeof value.retryable === "boolean" &&
    isStringArray(value.missingPermissions) &&
    isStringArray(value.missingIntegrations) &&
    Array.isArray(value.suggestedActions) &&
    value.suggestedActions.every(isSuggestedCommand)
  );
}

function isApprovalCard(value: UnknownRecord): boolean {
  return (
    hasCardBase(value, "approval") &&
    hasOnlyKeys(value, [
      "cardId",
      "kind",
      "mode",
      "approvalId",
      "changeSetId",
      "title",
      "risk",
      "state",
      "requestAction",
    ]) &&
    typeof value.approvalId === "string" &&
    value.approvalId.length >= 3 &&
    typeof value.changeSetId === "string" &&
    value.changeSetId.length >= 3 &&
    isNonEmptyString(value.title) &&
    ["low", "medium", "high", "critical"].includes(String(value.risk)) &&
    ["requested", "waiting", "approved", "rejected", "expired"].includes(
      String(value.state),
    ) &&
    (value.requestAction === undefined || validateAssistantAction(value.requestAction).ok)
  );
}

function isActionCard(value: UnknownRecord): boolean {
  const common = ["cardId", "kind", "mode", "title", "description", "action"];
  const descriptionValid = value.kind === "open_in_tool"
    ? typeof value.description === "string"
    : value.description === undefined || typeof value.description === "string";
  return (
    (hasCardBase(value, "open_in_tool") ||
      hasCardBase(value, "assistant_action")) &&
    hasOnlyKeys(value, common) &&
    isNonEmptyString(value.title) &&
    descriptionValid &&
    validateAssistantAction(value.action).ok
  );
}

function isCard(value: unknown): boolean {
  return (
    isRecord(value) &&
    (isProgressCard(value) ||
      isArtifactCard(value) ||
      isErrorCard(value) ||
      isApprovalCard(value) ||
      isActionCard(value))
  );
}

function isMessage(value: unknown): value is ConversationMessage {
  return (
    isRecord(value) &&
    hasOnlyKeys(value, [
      "messageId",
      "role",
      "body",
      "createdAt",
      "mode",
      "status",
      "replyToMessageId",
      "attachments",
      "cards",
    ]) &&
    typeof value.messageId === "string" &&
    /^msg_[A-Za-z0-9_-]+$/.test(value.messageId) &&
    ["user", "assistant", "system"].includes(String(value.role)) &&
    typeof value.body === "string" &&
    isUtcTimestamp(value.createdAt) &&
    isExecutionMode(value.mode) &&
    ["complete", "streaming", "failed", "cancelled"].includes(
      String(value.status),
    ) &&
    (value.replyToMessageId === undefined ||
      (typeof value.replyToMessageId === "string" &&
        /^msg_[A-Za-z0-9_-]+$/.test(value.replyToMessageId))) &&
    Array.isArray(value.attachments) &&
    value.attachments.every(isAttachment) &&
    Array.isArray(value.cards) &&
    value.cards.every(isCard)
  );
}

export function isConversationRecord(value: unknown): value is ConversationRecord {
  return (
    isRecord(value) &&
    hasOnlyKeys(value, [
      "schemaVersion",
      "conversationId",
      "scope",
      "messages",
      "executionMode",
      "updatedAt",
      "activeRunId",
    ]) &&
    value.schemaVersion === 1 &&
    typeof value.conversationId === "string" &&
    /^cnv_[A-Za-z0-9_-]+$/.test(value.conversationId) &&
    isScope(value.scope) &&
    Array.isArray(value.messages) &&
    value.messages.every(isMessage) &&
    isExecutionMode(value.executionMode) &&
    isUtcTimestamp(value.updatedAt) &&
    (value.activeRunId === undefined ||
      value.activeRunId === null ||
      (typeof value.activeRunId === "string" &&
        /^run_[A-Za-z0-9_-]+$/.test(value.activeRunId)))
  );
}
