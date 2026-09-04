import { openLogicEditorCommand } from "./openLogicEditor.ts";

export type LogicCommandDefinition = {
  id: string;
  title: string;
  requiredPermissions: string[];
  requiredIntegrations?: string[];
  requiresApproval?: boolean;
};

export const logicCommandDefinitions: LogicCommandDefinition[] = [
  openLogicEditorCommand,
  { id: "logic.graph.validate", title: "验证玩法图", requiredPermissions: ["logic:read"] },
  { id: "logic.interaction.compile", title: "编译交互模板", requiredPermissions: ["logic:write"] },
  { id: "logic.test_plan.generate", title: "生成逻辑测试", requiredPermissions: ["logic:read", "logic:test"] },
  { id: "logic.code_change.propose", title: "创建 C# ChangeSet", requiredPermissions: ["logic:write", "logic:code:review"] },
  { id: "logic.code_change.approve", title: "批准 C# ChangeSet", requiredPermissions: ["logic:code:approve"], requiresApproval: true },
  { id: "logic.code_change.apply", title: "应用已批准的 C# ChangeSet", requiredPermissions: ["logic:code:approve"], requiredIntegrations: ["unity"], requiresApproval: true },
  { id: "logic.code_change.rollback", title: "回滚 C# ChangeSet", requiredPermissions: ["logic:code:approve"], requiredIntegrations: ["unity"], requiresApproval: true },
];
