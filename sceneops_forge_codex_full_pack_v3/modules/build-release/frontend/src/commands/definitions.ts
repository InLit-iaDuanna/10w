export interface CommandAvailabilityContext {
  permissions: ReadonlySet<string>;
  integrations: ReadonlySet<string>;
  blockingGateCount: number;
  approvalScopeValid: boolean;
}

const command = (
  id: string,
  title: string,
  permission: string,
  requiredIntegrations: readonly string[] = [],
  approvalRequired = false,
) => ({ id, title, requiredPermissions: [permission], requiredIntegrations, approvalRequired });

export const commandDefinitions = [
  command("build.matrix.create", "创建构建矩阵", "build:record"),
  command("build.manifest.record", "记录构建清单", "build:record", ["artifact-store"]),
  command("release.candidate.create", "创建发布候选", "release:write", ["artifact-store"]),
  command("release.candidate.approve", "审批发布候选", "release:approve", [], true),
  command("release.patch-note.generate", "生成补丁说明", "release:write"),
  command("release.patch-note.edit", "编辑补丁说明", "release:write"),
  command("release.deploy", "部署候选", "release:deploy", ["artifact-store"], true),
  command("release.deploy.retry", "重试部署", "release:deploy", ["artifact-store"], true),
  command("release.rollback.plan", "创建回滚计划", "release:rollback", ["artifact-store"]),
  command("release.rollback.execute", "执行回滚", "release:rollback", ["artifact-store"], true),
] as const;

export function commandAvailability(
  commandId: string,
  context: CommandAvailabilityContext,
): Readonly<{ enabled: boolean; reason?: string }> {
  const definition = commandDefinitions.find((item) => item.id === commandId);
  if (!definition) return { enabled: false, reason: "未知命令" };
  const missingPermission = definition.requiredPermissions.find(
    (permission) => !context.permissions.has(permission),
  );
  if (missingPermission) return { enabled: false, reason: `缺少权限：${missingPermission}` };
  const missingIntegration = definition.requiredIntegrations.find(
    (integration) => !context.integrations.has(integration),
  );
  if (missingIntegration) return { enabled: false, reason: `集成离线：${missingIntegration}` };
  if (
    (commandId === "release.deploy" || commandId === "release.rollback.execute") &&
    context.blockingGateCount > 0
  ) {
    return { enabled: false, reason: "存在阻断门禁" };
  }
  if (definition.approvalRequired && !context.approvalScopeValid) {
    return { enabled: false, reason: "需要与当前作用域匹配的审批" };
  }
  return { enabled: true };
}
