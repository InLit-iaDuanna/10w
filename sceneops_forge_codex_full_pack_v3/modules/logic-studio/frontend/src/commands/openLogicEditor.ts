import type { LogicContext, LogicEditorId } from "../editors/editorTypes.ts";

export type LogicEditorTarget =
  | "feature"
  | "state_graph"
  | "interaction_graph"
  | "quest_dialogue"
  | "code_diff"
  | "test_cases";

export type OpenLogicEditorInput = {
  target: LogicEditorTarget;
  placement?:
    | { mode: "tab" | "replace" | "floating" | "popout" }
    | {
        mode: "split";
        direction: "left" | "right" | "above" | "below";
        relativeToInstanceId?: string;
      };
  context?: LogicContext;
};

export type OpenLogicEditorAction = {
  type: "workbench.open_editor";
  editorId: LogicEditorId;
  placement:
    | { mode: "tab" | "replace" | "floating" | "popout" }
    | {
        mode: "split";
        direction: "left" | "right" | "above" | "below";
        relativeToInstanceId?: string;
      };
  context?: LogicContext;
  requireConfirmation: true;
};

const EDITOR_IDS: Record<LogicEditorTarget, LogicEditorId> = {
  feature: "logic.feature",
  state_graph: "logic.state_graph",
  interaction_graph: "logic.interaction_graph",
  quest_dialogue: "logic.quest_dialogue",
  code_diff: "logic.code_diff",
  test_cases: "logic.test_cases",
};

export function createOpenLogicEditorAction(
  input: OpenLogicEditorInput,
): OpenLogicEditorAction {
  return {
    type: "workbench.open_editor",
    editorId: EDITOR_IDS[input.target],
    placement: input.placement ?? { mode: "split", direction: "right" },
    ...(input.context ? { context: structuredClone(input.context) } : {}),
    requireConfirmation: true,
  };
}

export const openLogicEditorCommand = {
  id: "logic.editor.open",
  title: "打开逻辑工具",
  requiredPermissions: ["logic:read"],
  createAction: createOpenLogicEditorAction,
};
