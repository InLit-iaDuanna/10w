export interface WorldCommandDefinition {
  id: string;
  title: string;
  requiredPermissions: string[];
  requiredIntegrations: string[];
  mutatesProductionData: boolean;
  implementation: string;
}

export interface WorldCommandAccessProjection {
  moduleEnabled: boolean;
  permissions: ReadonlySet<string>;
  connectedIntegrations: ReadonlySet<string>;
}

export interface WorldCommandAvailability {
  available: boolean;
  state: 'available' | 'module-disabled' | 'permission-denied' | 'disconnected';
  message: string;
}

export function evaluateWorldCommandAvailability(
  definition: WorldCommandDefinition,
  access: WorldCommandAccessProjection,
): WorldCommandAvailability {
  if (!access.moduleEnabled) {
    return { available: false, state: 'module-disabled', message: 'World Composer is disabled.' };
  }
  const missingPermission = definition.requiredPermissions.find(
    (permission) => !access.permissions.has(permission),
  );
  if (missingPermission) {
    return {
      available: false,
      state: 'permission-denied',
      message: `Missing permission: ${missingPermission}`,
    };
  }
  const missingIntegration = definition.requiredIntegrations.find(
    (integration) => !access.connectedIntegrations.has(integration),
  );
  if (missingIntegration) {
    return {
      available: false,
      state: 'disconnected',
      message: `Integration is not connected: ${missingIntegration}`,
    };
  }
  return { available: true, state: 'available', message: 'Command is available.' };
}

export const worldCommandDefinitions: WorldCommandDefinition[] = [
  {
    id: 'scene.annotation.create',
    title: '创建空间标注',
    requiredPermissions: ['scene:annotate'],
    requiredIntegrations: [],
    mutatesProductionData: false,
    implementation: 'validateAnnotation',
  },
  {
    id: 'scene.object.place.propose',
    title: '提出对象放置变更',
    requiredPermissions: ['scene:write'],
    requiredIntegrations: [],
    mutatesProductionData: true,
    implementation: 'createAssetPlacementPlan',
  },
  {
    id: 'scene.issue.restore',
    title: '恢复问题空间上下文',
    requiredPermissions: ['scene:read'],
    requiredIntegrations: [],
    mutatesProductionData: false,
    implementation: 'restoreIssueContext',
  },
  {
    id: 'scene.capture.fixed.request',
    title: '请求固定相机捕获',
    requiredPermissions: ['scene:read'],
    requiredIntegrations: ['artifact-store'],
    mutatesProductionData: false,
    implementation: 'createFixedCameraCaptureRequest',
  },
  {
    id: 'scene.level.validate',
    title: '运行关卡门禁',
    requiredPermissions: ['scene:validate'],
    requiredIntegrations: [],
    mutatesProductionData: false,
    implementation: 'validateLevel',
  },
  {
    id: 'scene.world.update.propose',
    title: '提出世界图变更',
    requiredPermissions: ['scene:write'],
    requiredIntegrations: [],
    mutatesProductionData: true,
    implementation: 'createWorldGraphUpdatePlan',
  },
  {
    id: 'scene.recipe.apply.propose',
    title: '提出配方放置变更',
    requiredPermissions: ['scene:write'],
    requiredIntegrations: [],
    mutatesProductionData: true,
    implementation: 'compilePlacementRecipe',
  },
];
