import type {
  EditorAvailability,
  EditorDefinition,
  JsonValue,
  LazyEditorModule,
} from '../contracts.ts';

export interface EditorEnvironment {
  permissions: ReadonlySet<string>;
  connectedIntegrations: ReadonlySet<string>;
}

export class EditorRegistry {
  readonly #definitions = new Map<string, EditorDefinition>();
  readonly #loads = new Map<string, Promise<LazyEditorModule>>();

  register(definition: EditorDefinition): void {
    if (this.#definitions.has(definition.id)) {
      throw new Error(`Editor already registered: ${definition.id}`);
    }
    this.#definitions.set(definition.id, definition);
  }

  registerAll(definitions: readonly EditorDefinition[]): void {
    for (const definition of definitions) this.register(definition);
  }

  get(editorId: string): EditorDefinition {
    const definition = this.#definitions.get(editorId);
    if (!definition) throw new Error(`Unknown editor: ${editorId}`);
    return definition;
  }

  list(): EditorDefinition[] {
    return [...this.#definitions.values()];
  }

  availability(editorId: string, environment: EditorEnvironment): EditorAvailability {
    const definition = this.get(editorId);
    const missingPermissions = (definition.requiredPermissions ?? []).filter(
      (permission) => !environment.permissions.has(permission),
    );
    const missingIntegrations = (definition.requiredIntegrations ?? []).filter(
      (integration) => !environment.connectedIntegrations.has(integration),
    );
    if (missingPermissions.length > 0) {
      return {
        status: 'permission-denied',
        missingPermissions,
        missingIntegrations: [],
        message: `缺少权限：${missingPermissions.join('、')}`,
        suggestedActions: ['permission.request'],
      };
    }
    if (missingIntegrations.length > 0) {
      return {
        status: 'offline',
        missingPermissions: [],
        missingIntegrations,
        message: `集成未连接：${missingIntegrations.join('、')}`,
        suggestedActions: ['integration.open', 'run.retry'],
      };
    }
    return {
      status: 'available',
      missingPermissions: [],
      missingIntegrations: [],
      message: null,
      suggestedActions: [],
    };
  }

  load(editorId: string): Promise<LazyEditorModule> {
    const existing = this.#loads.get(editorId);
    if (existing) return existing;
    const load = this.get(editorId).load();
    this.#loads.set(editorId, load);
    load.catch(() => this.#loads.delete(editorId));
    return load;
  }

  initialState(editorId: string): JsonValue {
    return this.get(editorId).initialState();
  }

  restoreState(editorId: string, value: JsonValue): JsonValue {
    return this.get(editorId).restoreState(value);
  }
}
