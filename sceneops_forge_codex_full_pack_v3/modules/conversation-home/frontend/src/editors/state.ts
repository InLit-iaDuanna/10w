import type { JsonValue } from "../contracts/json.ts";
import type { ConversationAttachment } from "../conversation/types.ts";

export interface ConversationEditorState {
  composerDraft: string;
  pendingAttachments: ConversationAttachment[];
}

export const defaultConversationEditorState: ConversationEditorState = {
  composerDraft: "",
  pendingAttachments: [],
};

function isRecord(value: unknown): value is Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function isAttachment(value: unknown): value is ConversationAttachment {
  return (
    isRecord(value) &&
    Object.keys(value).every((key) =>
      ["attachmentId", "kind", "name", "mediaType", "sizeBytes"].includes(key),
    ) &&
    typeof value.attachmentId === "string" &&
    /^att_[A-Za-z0-9_-]+$/.test(value.attachmentId) &&
    (value.kind === "file" || value.kind === "project") &&
    typeof value.name === "string" &&
    value.name.length > 0 &&
    (value.mediaType === undefined || typeof value.mediaType === "string") &&
    (value.sizeBytes === undefined ||
      (Number.isInteger(value.sizeBytes) && Number(value.sizeBytes) >= 0))
  );
}

export function restoreConversationEditorState(
  value: unknown,
): ConversationEditorState {
  if (!isRecord(value)) {
    return defaultConversationEditorState;
  }

  if (
    !Object.keys(value).every((key) =>
      ["composerDraft", "pendingAttachments"].includes(key),
    ) ||
    typeof value.composerDraft !== "string" ||
    !Array.isArray(value.pendingAttachments) ||
    !value.pendingAttachments.every(isAttachment)
  ) {
    return defaultConversationEditorState;
  }

  return value as unknown as ConversationEditorState;
}

export function serializeConversationEditorState(
  state: ConversationEditorState,
): JsonValue {
  const serialized: ConversationEditorState = {
    composerDraft: state.composerDraft,
    pendingAttachments: state.pendingAttachments.map((attachment) => ({
      attachmentId: attachment.attachmentId,
      kind: attachment.kind,
      name: attachment.name,
      ...(attachment.mediaType ? { mediaType: attachment.mediaType } : {}),
      ...(attachment.sizeBytes === undefined
        ? {}
        : { sizeBytes: attachment.sizeBytes }),
    })),
  };
  return serialized as unknown as JsonValue;
}
