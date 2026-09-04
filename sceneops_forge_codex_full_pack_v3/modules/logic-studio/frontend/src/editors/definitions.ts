import type { LogicEditorDefinition } from "./editorTypes.ts";
import {
  restoreLogicEditorState,
  serializeLogicEditorState,
} from "./state.ts";

const loadRuntime = () => import("./LogicEditorRuntime.ts");

function defineEditor(
  definition: Omit<
    LogicEditorDefinition,
    "category" | "load" | "serializeState" | "restoreState" | "supportsContextBinding"
  >,
): LogicEditorDefinition {
  return {
    ...definition,
    category: "logic",
    supportsContextBinding: true,
    load: loadRuntime,
    serializeState: serializeLogicEditorState,
    restoreState: restoreLogicEditorState,
  };
}

export const logicEditorDefinitions: LogicEditorDefinition[] = [
  defineEditor({
    id: "logic.feature",
    title: "功能规格",
    icon: "document-check",
    defaultPlacement: "center",
    minWidth: 420,
    minHeight: 280,
    singleton: false,
    requiredPermissions: ["logic:read"],
    optionalIntegrations: [],
    emptyMessage: "尚未选择已批准的功能规格。",
  }),
  defineEditor({
    id: "logic.state_graph",
    title: "玩法状态图",
    icon: "graph-nodes",
    defaultPlacement: "center",
    minWidth: 520,
    minHeight: 360,
    singleton: false,
    requiredPermissions: ["logic:read"],
    optionalIntegrations: [],
    emptyMessage: "当前功能还没有 GameplayGraph。",
  }),
  defineEditor({
    id: "logic.interaction_graph",
    title: "交互关系图",
    icon: "link",
    defaultPlacement: "right",
    minWidth: 420,
    minHeight: 320,
    singleton: false,
    requiredPermissions: ["logic:read"],
    optionalIntegrations: ["unity"],
    emptyMessage: "当前图中还没有交互关系。",
  }),
  defineEditor({
    id: "logic.quest_dialogue",
    title: "任务与对话图",
    icon: "messages-square",
    defaultPlacement: "right",
    minWidth: 460,
    minHeight: 340,
    singleton: false,
    requiredPermissions: ["logic:read", "logic:write"],
    optionalIntegrations: [],
    emptyMessage: "当前功能还没有任务或对话节点。",
  }),
  defineEditor({
    id: "logic.code_diff",
    title: "代码差异",
    icon: "file-diff",
    defaultPlacement: "right",
    minWidth: 520,
    minHeight: 320,
    singleton: false,
    requiredPermissions: ["logic:read", "logic:code:review"],
    optionalIntegrations: ["unity"],
    emptyMessage: "尚未创建 C# ChangeSet 提案。",
  }),
  defineEditor({
    id: "logic.test_cases",
    title: "测试用例",
    icon: "flask-conical",
    defaultPlacement: "bottom",
    minWidth: 480,
    minHeight: 260,
    singleton: false,
    requiredPermissions: ["logic:read", "logic:test"],
    optionalIntegrations: ["unity"],
    emptyMessage: "当前图还没有生成测试引用。",
  }),
];
