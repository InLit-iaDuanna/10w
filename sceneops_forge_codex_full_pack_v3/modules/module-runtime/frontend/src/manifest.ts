export type ModuleStatus = "active" | "experimental" | "deprecated";
export type ModuleAvailability = "enabled" | "disabled" | "blocked";

export interface ModuleManifest {
  readonly schema_version: 1;
  readonly id: string;
  readonly version: string;
  readonly title: string;
  readonly description: string;
  readonly status: ModuleStatus;
  readonly feature_flag: string;
  readonly requires: {
    readonly modules: readonly string[];
    readonly integrations: readonly string[];
    readonly optional_integrations: readonly string[];
  };
  readonly contributes: {
    readonly editors: readonly string[];
    readonly commands: readonly string[];
    readonly events: readonly string[];
    readonly jobs: readonly string[];
    readonly workflows: readonly string[];
    readonly policy_gates: readonly string[];
  };
  readonly permissions: readonly string[];
  readonly entrypoints: {
    readonly frontend?: string;
    readonly backend?: string;
  };
}

export interface ModuleContribution {
  readonly manifest: ModuleManifest;
  readonly editors?: readonly unknown[];
  readonly commands?: readonly unknown[];
  readonly events?: readonly unknown[];
  readonly jobs?: readonly unknown[];
}

export interface ModuleRuntimeState {
  readonly moduleId: string;
  readonly featureFlag: string;
  readonly availability: ModuleAvailability;
  readonly missingRequiredIntegrations: readonly string[];
  readonly missingOptionalIntegrations: readonly string[];
  readonly blockingDependencies: readonly string[];
  readonly message: string;
}

export function resolveFrontendModuleStates(
  manifests: readonly ModuleManifest[],
  featureFlags: Readonly<Record<string, boolean>> = {},
  availableIntegrations: ReadonlySet<string> = new Set(),
): ReadonlyMap<string, ModuleRuntimeState> {
  const knownFlags = new Set(manifests.map((manifest) => manifest.feature_flag));
  const unknownFlags = Object.keys(featureFlags).filter((flag) => !knownFlags.has(flag));
  if (unknownFlags.length > 0) {
    throw new Error(`UNKNOWN_FEATURE_FLAGS: ${unknownFlags.sort().join(", ")}`);
  }

  const states = new Map<string, ModuleRuntimeState>();
  for (const manifest of manifests) {
    const missingRequiredIntegrations = manifest.requires.integrations
      .filter((integration) => !availableIntegrations.has(integration))
      .toSorted();
    const missingOptionalIntegrations = manifest.requires.optional_integrations
      .filter((integration) => !availableIntegrations.has(integration))
      .toSorted();
    const blockingDependencies = manifest.requires.modules
      .filter((dependency) => states.get(dependency)?.availability !== "enabled")
      .toSorted();

    let availability: ModuleAvailability;
    let message: string;
    if (featureFlags[manifest.feature_flag] === false) {
      availability = "disabled";
      message = "功能已由特性开关关闭。";
    } else if (blockingDependencies.length > 0) {
      availability = "blocked";
      message = `依赖模块不可用：${blockingDependencies.join("、")}`;
    } else if (missingRequiredIntegrations.length > 0) {
      availability = "blocked";
      message = `缺少必需集成：${missingRequiredIntegrations.join("、")}`;
    } else {
      availability = "enabled";
      message =
        missingOptionalIntegrations.length > 0
          ? `已启用；可选集成不可用：${missingOptionalIntegrations.join("、")}`
          : "已启用。";
    }
    states.set(manifest.id, {
      moduleId: manifest.id,
      featureFlag: manifest.feature_flag,
      availability,
      missingRequiredIntegrations,
      missingOptionalIntegrations,
      blockingDependencies,
      message,
    });
  }
  return states;
}
