export type EditorPlacement = "center" | "left" | "right" | "bottom";

export interface EditorDefinition {
  readonly id: string;
  readonly title: string;
  readonly icon: string;
  readonly category: "review";
  readonly load: () => Promise<{ default: unknown }>;
  readonly defaultPlacement: EditorPlacement;
  readonly minWidth: number;
  readonly minHeight: number;
  readonly singleton: boolean;
  readonly requiredPermissions: readonly string[];
  readonly requiredIntegrations: readonly string[];
  readonly optionalIntegrations: readonly string[];
  readonly supportsContextBinding: true;
  readonly serializeState: (state: unknown) => unknown;
  readonly restoreState: (value: unknown) => unknown;
}

export interface CommandContext {
  readonly permissions: ReadonlySet<string>;
  readonly integrations: ReadonlySet<string>;
}

export interface CommandExecutionContext extends CommandContext {
  readonly versionCollaborationApi: import("./api.ts").VersionCollaborationApi;
}

export interface CommandAvailability {
  readonly available: boolean;
  readonly reason?: string;
}

export interface WorkbenchCommandDefinition {
  readonly id: string;
  readonly title: string;
  readonly requiredPermissions: readonly string[];
  readonly requiredIntegrations: readonly string[];
  readonly inputSchema: {
    readonly parse: (value: unknown) => unknown;
  };
  readonly canExecute: (context: CommandContext) => CommandAvailability;
  readonly execute: (context: CommandExecutionContext, input: unknown) => Promise<unknown>;
}

export interface WorkspacePresetContribution {
  readonly id: "review";
  readonly title: string;
  readonly activateOnFreshLaunch: false;
  readonly areas: readonly {
    readonly editorId: string;
    readonly placement: EditorPlacement;
    readonly relativeTo?: string;
  }[];
}

export interface ToolLibraryEntry {
  readonly editorId: string;
  readonly group: string;
  readonly keywords: readonly string[];
  readonly recommendedEdges: readonly ("right" | "bottom")[];
}

export interface ModuleContribution {
  readonly manifest: ModuleManifest;
  readonly editors: readonly EditorDefinition[];
  readonly commands: readonly WorkbenchCommandDefinition[];
  readonly workspacePresets: readonly WorkspacePresetContribution[];
  readonly navigation: readonly ToolLibraryEntry[];
}

export interface ModuleManifest {
  readonly schemaVersion: 1;
  readonly id: "version-collaboration";
  readonly version: string;
  readonly featureFlag: "version_collaboration";
}
