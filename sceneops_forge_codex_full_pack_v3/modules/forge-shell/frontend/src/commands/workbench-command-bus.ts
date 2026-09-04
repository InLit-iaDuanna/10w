import type {
  CommandAvailability,
  CommandExecutionContext,
  WorkbenchCommandDefinition,
} from '../contracts.ts';

export class CommandRejectedError extends Error {
  readonly code: 'UNKNOWN_COMMAND' | 'INVALID_INPUT' | 'UNAVAILABLE';

  constructor(code: CommandRejectedError['code'], message: string) {
    super(message);
    this.name = 'CommandRejectedError';
    this.code = code;
  }
}
export class WorkbenchCommandBus {
  readonly #commands = new Map<string, WorkbenchCommandDefinition<unknown, unknown>>();

  register<TInput, TResult>(definition: WorkbenchCommandDefinition<TInput, TResult>): void {
    if (this.#commands.has(definition.id)) throw new Error(`Command already registered: ${definition.id}`);
    this.#commands.set(definition.id, definition as WorkbenchCommandDefinition<unknown, unknown>);
  }

  availability(commandId: string, context: CommandExecutionContext, input: unknown): CommandAvailability {
    const definition = this.#commands.get(commandId);
    if (!definition) return { available: false, reason: `Unknown command: ${commandId}` };
    if (!definition.validate(input)) return { available: false, reason: 'Invalid command input' };
    const missingPermission = definition.requiredPermissions?.find(
      (permission) => !context.permissions.has(permission),
    );
    if (missingPermission) return { available: false, reason: `Missing permission: ${missingPermission}` };
    const missingIntegration = definition.requiredIntegrations?.find(
      (integration) => !context.connectedIntegrations.has(integration),
    );
    if (missingIntegration) return { available: false, reason: `Integration offline: ${missingIntegration}` };
    return definition.canExecute(context, input);
  }

  async execute<TResult>(commandId: string, context: CommandExecutionContext, input: unknown): Promise<TResult> {
    const definition = this.#commands.get(commandId);
    if (!definition) throw new CommandRejectedError('UNKNOWN_COMMAND', `Unknown command: ${commandId}`);
    if (!definition.validate(input)) throw new CommandRejectedError('INVALID_INPUT', 'Invalid command input');
    const availability = this.availability(commandId, context, input);
    if (!availability.available) {
      throw new CommandRejectedError('UNAVAILABLE', availability.reason ?? 'Command unavailable');
    }
    return definition.execute(context, input) as Promise<TResult>;
  }
}
