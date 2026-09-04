import type { ExecutionMode, ProjectBible } from "../contracts.ts";
import type { DesignEditorAccess, DesignEditorBlockedView } from "./editorAccess.ts";
import { resolveDesignEditorBlock } from "./editorAccess.ts";

export interface ProjectBibleEditorView {
  readonly state: "empty" | "ready";
  readonly title: string;
  readonly message: string;
  readonly mode: ExecutionMode;
  readonly sections: readonly string[];
}

export default function buildProjectBibleEditorView(
  access: DesignEditorAccess,
  bible: ProjectBible | null,
  mode: ExecutionMode,
): ProjectBibleEditorView | DesignEditorBlockedView {
  const blocked = resolveDesignEditorBlock(access);
  if (blocked !== null) return blocked;
  if (bible === null) {
    return { state: "empty", title: "尚无 Project Bible", message: "从已确认的项目入口创建结构化 Bible。", mode: "planned", sections: [] };
  }
  return {
    state: "ready",
    title: bible.title,
    message: bible.status === "approved" ? "项目规则已批准。" : "项目规则仍可编辑或送审。",
    mode,
    sections: ["游戏目标", "目标玩家", "核心循环", "视觉规则", "音频规则", "交互规则", "命名规则", "平台预算", "禁止修改", "批准决策"],
  };
}
