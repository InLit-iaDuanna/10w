export type ComposerKeyboardIntent =
  | "send"
  | "newline"
  | "cancel_stream"
  | "open_command_search"
  | "open_slash_commands"
  | "none";

export interface ComposerKeyboardInput {
  key: string;
  value: string;
  shiftKey: boolean;
  controlKey: boolean;
  metaKey: boolean;
  isComposing: boolean;
  isStreaming: boolean;
}

export function resolveComposerKeyboardIntent(
  input: ComposerKeyboardInput,
): ComposerKeyboardIntent {
  if (input.isComposing) {
    return "none";
  }

  if (input.key.toLowerCase() === "k" && (input.controlKey || input.metaKey)) {
    return "open_command_search";
  }

  if (input.key === "/" && input.value.length === 0) {
    return "open_slash_commands";
  }

  if (input.key === "Escape" && input.isStreaming) {
    return "cancel_stream";
  }

  if (input.key === "Enter") {
    return input.shiftKey ? "newline" : "send";
  }

  return "none";
}

export interface CommandSearchPort {
  execute(
    commandId: "workbench.command_search.open",
    input: { mode: "all" | "slash"; initialQuery: string },
  ): Promise<unknown>;
}

export function createCommandSearchRequest(mode: "all" | "slash") {
  return {
    commandId: "workbench.command_search.open" as const,
    input: { mode, initialQuery: mode === "slash" ? "/" : "" },
  };
}

export async function handoffComposerSearch(
  commands: CommandSearchPort,
  intent: "open_command_search" | "open_slash_commands",
): Promise<void> {
  const request = createCommandSearchRequest(
    intent === "open_slash_commands" ? "slash" : "all",
  );
  await commands.execute(request.commandId, request.input);
}
