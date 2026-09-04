import {
  AssistantActionCoordinator,
  type CommandAvailability,
  type CommandRequest,
  type WorkbenchCommandBusPort,
  type WorkbenchContextSnapshot,
} from "../assistant-actions/coordinator.ts";
import type { AssistantAction } from "../assistant-actions/types.ts";
import type { ConversationAttachmentStager } from "../composer/attachments.ts";
import { createCommandSearchRequest } from "../composer/keyboard.ts";
import type { SuggestedCommand } from "../conversation/cards.ts";
import type {
  ConversationController,
  ConversationOperationResult,
} from "../conversation/controller.ts";
import type { ConversationAttachment } from "../conversation/types.ts";
import type { WorkbenchContextSummary } from "../conversation/types.ts";
import type {
  ConversationAvailability,
  ConversationEditorRuntime,
} from "./runtime.ts";

export interface ConversationRuntimeDependencies {
  controller: ConversationController;
  commandBus: WorkbenchCommandBusPort;
  getWorkbenchContext(): WorkbenchContextSnapshot;
  getContextSummary(): WorkbenchContextSummary;
  getConversationAvailability(): ConversationAvailability;
  attachmentStager: ConversationAttachmentStager;
}

export class WorkbenchCommandUnavailableError extends Error {
  readonly availability: CommandAvailability;

  constructor(availability: CommandAvailability) {
    super(availability.message ?? "Workbench 命令当前不可用。");
    this.name = "WorkbenchCommandUnavailableError";
    this.availability = availability;
  }
}

async function executeCheckedCommand(
  commandBus: WorkbenchCommandBusPort,
  request: CommandRequest,
  context: WorkbenchContextSnapshot,
): Promise<void> {
  const availability = await commandBus.inspect(request, context);
  const approvalReady =
    !availability.approval.required || availability.approval.state === "approved";
  if (availability.state === "unavailable" || !approvalReady) {
    throw new WorkbenchCommandUnavailableError(availability);
  }
  await commandBus.execute(request, context);
}

export function createConversationEditorRuntime(
  dependencies: ConversationRuntimeDependencies,
): ConversationEditorRuntime {
  const coordinator = new AssistantActionCoordinator(dependencies.commandBus);

  return {
    getSnapshot: () => dependencies.controller.snapshot,
    subscribe: (listener) => dependencies.controller.subscribe(listener),
    getAvailability: () => dependencies.getConversationAvailability(),
    getContextSummary: () => dependencies.getContextSummary(),
    stageAttachments: (sources) =>
      dependencies.attachmentStager.stage(sources, new AbortController().signal),
    send: (
      text: string,
      attachments: ConversationAttachment[],
    ): Promise<ConversationOperationResult> =>
      dependencies.controller.send(text, attachments),
    cancelStream: () => {
      dependencies.controller.cancel();
    },
    retry: (assistantMessageId: string): Promise<ConversationOperationResult> =>
      dependencies.controller.retry(assistantMessageId),
    openCommandSearch: async (mode) => {
      const request = createCommandSearchRequest(mode);
      await executeCheckedCommand(
        dependencies.commandBus,
        {
          ...request,
          source: { surface: "command_search" },
        },
        dependencies.getWorkbenchContext(),
      );
    },
    prepareAssistantAction: (action: AssistantAction) =>
      coordinator.prepare(
        action,
        "assistant",
        dependencies.getWorkbenchContext(),
      ),
    executeAssistantAction: (actionId, confirmLayout) =>
      confirmLayout
        ? coordinator.confirmLayoutAndExecute(
            actionId,
            dependencies.getWorkbenchContext(),
          )
        : coordinator.executePrepared(
            actionId,
            dependencies.getWorkbenchContext(),
          ),
    cancelAssistantAction: (actionId) => {
      coordinator.cancel(actionId);
    },
    executeSuggestedCommand: async (command: SuggestedCommand) => {
      await executeCheckedCommand(
        dependencies.commandBus,
        {
          commandId: command.commandId,
          input: command.input,
          source: { surface: "button" },
        },
        dependencies.getWorkbenchContext(),
      );
    },
  };
}
