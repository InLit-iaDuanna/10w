import type { StructuralDiffEntry } from "./contracts.ts";

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function pointerSegment(value: string): string {
  return value.replaceAll("~", "~0").replaceAll("/", "~1");
}

function childPath(parent: string, key: string): string {
  return `${parent}/${pointerSegment(key)}`;
}

function compare(before: unknown, after: unknown, path: string, entries: StructuralDiffEntry[]): void {
  if (Object.is(before, after)) return;
  if (Array.isArray(before) && Array.isArray(after)) {
    const length = Math.max(before.length, after.length);
    for (let index = 0; index < length; index += 1) {
      const itemPath = childPath(path, String(index));
      if (index >= before.length) entries.push({ path: itemPath, kind: "added", before: undefined, after: after[index] });
      else if (index >= after.length) entries.push({ path: itemPath, kind: "removed", before: before[index], after: undefined });
      else compare(before[index], after[index], itemPath, entries);
    }
    return;
  }
  if (isRecord(before) && isRecord(after)) {
    const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])].sort();
    for (const key of keys) {
      const itemPath = childPath(path, key);
      if (!(key in before)) entries.push({ path: itemPath, kind: "added", before: undefined, after: after[key] });
      else if (!(key in after)) entries.push({ path: itemPath, kind: "removed", before: before[key], after: undefined });
      else compare(before[key], after[key], itemPath, entries);
    }
    return;
  }
  entries.push({ path: path.length === 0 ? "/" : path, kind: "changed", before, after });
}

export function structuralDiff(before: unknown, after: unknown): readonly StructuralDiffEntry[] {
  const entries: StructuralDiffEntry[] = [];
  compare(before, after, "", entries);
  return entries;
}
