import type { ExecutionMode, GddDocument } from "../contracts.ts";
import type { DesignEditorAccess, DesignEditorBlockedView } from "./editorAccess.ts";
import { resolveDesignEditorBlock } from "./editorAccess.ts";

export interface GddEditorView {
  readonly state: "empty" | "ready";
  readonly title: string;
  readonly message: string;
  readonly mode: ExecutionMode;
  readonly systemCount: number;
  readonly dependencyCount: number;
}

export default function buildGddEditorView(
  access: DesignEditorAccess,
  gdd: GddDocument | null,
  mode: ExecutionMode,
): GddEditorView | DesignEditorBlockedView {
  const blocked = resolveDesignEditorBlock(access);
  if (blocked !== null) return blocked;
  if (gdd === null) {
    return { state: "empty", title: "尚无 GDD", message: "创建结构化玩法系统、进程和世界规则。", mode: "planned", systemCount: 0, dependencyCount: 0 };
  }
  return {
    state: "ready",
    title: gdd.title,
    message: `${gdd.gameplaySystems.length} 个玩法系统，${gdd.assumptions.length} 条假设。`,
    mode,
    systemCount: gdd.gameplaySystems.length,
    dependencyCount: gdd.dependencyIds.length,
  };
}
