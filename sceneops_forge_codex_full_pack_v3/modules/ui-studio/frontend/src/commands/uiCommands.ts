export type Availability = { available: boolean; reason?: "disabled" | "offline" | "permission" };
export type UiCommandInput = Record<string, string>;
export interface InputSchema<T> { parse(input: unknown): T; }
export interface UiCommandGateway { execute(commandId: string, input: UiCommandInput): Promise<unknown>; }
export interface UiCommandContext { enabled: boolean; unityOnline: boolean; permissions: readonly string[]; gateway: UiCommandGateway; }

const requiredTextSchema = (...fields: string[]): InputSchema<UiCommandInput> => ({
  parse(input: unknown): UiCommandInput {
    if (!input || typeof input !== "object" || Array.isArray(input)) throw new Error("命令输入必须是对象。");
    const parsed = input as Record<string, unknown>;
    for (const field of fields) {
      const value = parsed[field];
      if (typeof value !== "string" || !value.trim()) throw new Error(`缺少有效字段：${field}`);
    }
    for (const [key, value] of Object.entries(parsed)) {
      if (!fields.includes(key)) throw new Error(`未知字段：${key}`);
      if (typeof value !== "string") throw new Error(`字段必须是字符串：${key}`);
    }
    return parsed as UiCommandInput;
  },
});
export const uiCommandSchemas = {
  validateFlow: requiredTextSchema("flowId"),
  proposeMapping: requiredTextSchema("mappingId", "changeSetId"),
  approveChangeSet: requiredTextSchema("changeSetId"),
  publishChangeSet: requiredTextSchema("changeSetId"),
};
export const uiModuleAvailability = (enabled: boolean): Availability => enabled ? { available: true } : { available: false, reason: "disabled" };
const canExecute = (context: UiCommandContext, permission: string, needsUnity = false): Availability => {
  if (!context.enabled) return { available: false, reason: "disabled" };
  if (!context.permissions.includes(permission)) return { available: false, reason: "permission" };
  return needsUnity && !context.unityOnline ? { available: false, reason: "offline" } : { available: true };
};
const defineCommand = (id: string, title: string, permission: string, inputSchema: InputSchema<UiCommandInput>, needsUnity = false) => ({
  id, title, requiredPermissions: [permission], inputSchema,
  canExecute: (context: UiCommandContext) => canExecute(context, permission, needsUnity),
  execute: async (context: UiCommandContext, input: unknown) => {
    const availability = canExecute(context, permission, needsUnity);
    if (!availability.available) throw new Error(`UI_COMMAND_UNAVAILABLE: ${availability.reason}`);
    return context.gateway.execute(id, inputSchema.parse(input));
  },
});
export const uiCommands = [
  defineCommand("ui.flow.validate", "验证 UI 流程", "ui:read", uiCommandSchemas.validateFlow),
  defineCommand("ui.mapping.propose", "提议 Unity UI 映射", "ui:write", uiCommandSchemas.proposeMapping, true),
  defineCommand("ui.changeset.approve", "批准 UI 变更", "ui:publish", uiCommandSchemas.approveChangeSet),
  defineCommand("ui.changeset.publish", "发布已批准的 UI 变更", "ui:publish", uiCommandSchemas.publishChangeSet, true),
] as const;
