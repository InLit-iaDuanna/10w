import type {
  BrowserAttachmentSource,
  BrowserFileSystemEntryHandle,
} from "./attachments.ts";

export function readDroppedEntries(
  dataTransfer: DataTransfer,
): BrowserAttachmentSource[] {
  const sources: BrowserAttachmentSource[] = [];
  for (const item of Array.from(dataTransfer.items)) {
    if (item.kind !== "file") {
      continue;
    }
    const file = item.getAsFile();
    const browserEntry = (
      item as unknown as {
        webkitGetAsEntry?: () => BrowserFileSystemEntryHandle | null;
      }
    ).webkitGetAsEntry?.();
    if (!file && !browserEntry) {
      continue;
    }
    sources.push({
      entry: {
        name: file?.name ?? browserEntry?.name ?? "",
        mediaType: file?.type || undefined,
        sizeBytes: file?.size,
        relativePath: file?.webkitRelativePath || undefined,
        isDirectory: browserEntry?.isDirectory ?? false,
      },
      ...(file ? { file } : {}),
      ...(browserEntry ? { browserEntry } : {}),
    });
  }
  return sources;
}
