import type { ConversationAttachment } from "../conversation/types.ts";

export interface DroppedEntryMetadata {
  name: string;
  mediaType?: string;
  sizeBytes?: number;
  relativePath?: string;
  isDirectory: boolean;
}

export interface BrowserFileEntryHandle {
  readonly isFile: true;
  readonly isDirectory: false;
  readonly name: string;
  readonly fullPath: string;
  file(
    success: (file: File) => void,
    failure?: (error: DOMException) => void,
  ): void;
}

export interface BrowserDirectoryEntryReader {
  readEntries(
    success: (entries: BrowserFileSystemEntryHandle[]) => void,
    failure?: (error: DOMException) => void,
  ): void;
}

export interface BrowserDirectoryEntryHandle {
  readonly isFile: false;
  readonly isDirectory: true;
  readonly name: string;
  readonly fullPath: string;
  createReader(): BrowserDirectoryEntryReader;
}

export type BrowserFileSystemEntryHandle =
  | BrowserFileEntryHandle
  | BrowserDirectoryEntryHandle;

export interface BrowserAttachmentSource {
  entry: DroppedEntryMetadata;
  file?: File;
  browserEntry?: BrowserFileSystemEntryHandle;
}

export interface ConversationAttachmentStager {
  stage(
    sources: BrowserAttachmentSource[],
    signal: AbortSignal,
  ): Promise<ConversationAttachment[]>;
}

export type AttachmentIdFactory = () => string;

export function toConversationAttachment(
  entry: DroppedEntryMetadata,
  createId: AttachmentIdFactory,
): ConversationAttachment {
  if (entry.name.trim().length === 0) {
    throw new Error("附件名称不能为空。");
  }
  if (
    entry.sizeBytes !== undefined &&
    (!Number.isInteger(entry.sizeBytes) || entry.sizeBytes < 0)
  ) {
    throw new Error("附件大小必须是非负整数。");
  }
  const attachmentId = createId();
  if (!/^att_[A-Za-z0-9_-]+$/.test(attachmentId)) {
    throw new Error("附件 adapter 必须返回 stable attachment ID。");
  }
  const isProject =
    entry.isDirectory ||
    Boolean(entry.relativePath && entry.relativePath.includes("/"));

  return {
    attachmentId,
    kind: isProject ? "project" : "file",
    name: entry.name,
    ...(entry.mediaType ? { mediaType: entry.mediaType } : {}),
    ...(entry.sizeBytes === undefined ? {} : { sizeBytes: entry.sizeBytes }),
  };
}
