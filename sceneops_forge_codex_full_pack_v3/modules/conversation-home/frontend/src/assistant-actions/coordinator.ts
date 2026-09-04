import type { ErrorCard, SuggestedCommand } from "../conversation/cards.ts";
import type { JsonObject, JsonValue } from "../contracts/json.ts";
import type { AssistantAction } from "./types.ts";
import { validateAssistantAction } from "./validate.ts";

export interface WorkbenchContextSnapshot {
  projectId: string | null;
  branchId: string | null;
  sceneId: string | null;
  selectedSceneObjectIds: string[];
  selectedAssetIds: string[];
  activeFeatureId: string | null;
  activeTaskId: string | null;
  activeChangeSetId: string | null;
  activeRenderJobId: string | null;
  activeBuildId: string | null;
  activePlaytestRunId: string | null;
  activeIssueId: string | null;
}

export type ActionOrigin = "assistant" | "button" | "menu" | "command_search";

export interface CommandRequest {
  commandId: string;
  input: JsonObject;
  source: {
    surface: ActionOrigin;
    assistantActionId?: string;
  };
}

export interface CommandAvailability {
  state: "available" | "unavailable";
  layoutEffect: "none" | "material";
  code?: string;
  message?: string;
  retryable?: boolean;
  missingPermissions: string[];
  missingIntegrations: string[];
  suggestedActions: SuggestedCommand[];
  approval: {
    required: boolean;
    state: "not_required" | "waiting" | "approved" | "rejected";
    approvalId?: string;
  };
}

export interface LayoutActionPreview {
  mode: "planned";
  summary: string;
  changes: string[];
  targetDescription: string;
}

export interface WorkbenchCommandBusPort {
  inspect(
    request: CommandRequest,
    context: WorkbenchContextSnapshot,
  ): Promise<CommandAvailability>;
  preview(
    request: CommandRequest,
    context: WorkbenchContextSnapshot,
  ): Promise<LayoutActionPreview>;
  execute<TResult extends JsonValue = JsonValue>(
    request: CommandRequest,
    context: WorkbenchContextSnapshot,
  ): Promise<TResult>;
}

export type PreparedAction =
  | {
      status: "ready";
      action: AssistantAction;
      origin: ActionOrigin;
    }
  | {
      status: "awaiting_confirmation";
      action: AssistantAction;
      origin: ActionOrigin;
      preview: LayoutActionPreview;
    }
  | {
      status: "waiting_approval";
      action: AssistantAction;
      origin: ActionOrigin;
      approvalId?: string;
    }
  | {
      status: "invalid" | "unavailable";
      error: ErrorCard;
    };

export type ActionExecutionResult =
  | { status: "executed"; result: JsonValue }
  | { status: "waiting_approval"; approvalId?: string }
  | { status: "rejected"; error: ErrorCard };

interface PendingAction {
  action: AssistantAction;
  origin: ActionOrigin;
  layoutConfirmationRequired: boolean;
}

function toJsonObject(input: object): JsonObject {
  return structuredClone(input) as JsonObject;
}

function cloneAction(action: AssistantAction): AssistantAction {
  return structuredClone(action);
}

function toCommandRequest(
  action: AssistantAction,
  origin: ActionOrigin,
): CommandRequest {
  return {
    commandId: action.type,
    input: toJsonObject(action.input),
    source: {
      surface: origin,
      assistantActionId: action.actionId,
    },
  };
}

function errorCard(
  actionId: string,
  code: string,
  message: string,
  availability?: CommandAvailability,
): ErrorCard {
  return {
    cardId: `card_${actionId.replace(/^act_/, "")}_error`,
    kind: "error",
    mode: "blocked",
    code,
    message,
    retryable:
      availability?.retryable ?? code === "COMMAND_TEMPORARILY_UNAVAILABLE",
    missingPermissions: availability?.missingPermissions ?? [],
    missingIntegrations: availability?.missingIntegrations ?? [],
    suggestedActions: availability?.suggestedActions ?? [],
  };
}

function unavailableError(
  action: AssistantAction,
  availability: CommandAvailability,
): ErrorCard {
  return errorCard(
    action.actionId,
    availability.code ?? "COMMAND_UNAVAILABLE",
    availability.message ?? "当前无法执行该操作。",
    availability,
  );
}

export class AssistantActionCoordinator {
  readonly #pending = new Map<string, PendingAction>();
  readonly #commandBus: WorkbenchCommandBusPort;

  constructor(commandBus: WorkbenchCommandBusPort) {
    this.#commandBus = commandBus;
  }

  async prepare(
    candidate: unknown,
    origin: ActionOrigin,
    context: WorkbenchContextSnapshot,
  ): Promise<PreparedAction> {
    const validated = validateAssistantAction(candidate);
    if (!validated.ok) {
      return {
        status: "invalid",
        error: errorCard(
          "act_invalid",
          "ASSISTANT_ACTION_INVALID",
          validated.issues.map((issue) => `${issue.path}: ${issue.message}`).join("；"),
        ),
      };
    }

    const action = cloneAction(validated.value);
    if (this.#pending.has(action.actionId)) {
      return {
        status: "invalid",
        error: errorCard(
          action.actionId,
          "ASSISTANT_ACTION_ID_CONFLICT",
          "相同 actionId 的操作仍在等待处理。",
        ),
      };
    }
    const request = toCommandRequest(action, origin);
    const availability = await this.#commandBus.inspect(request, context);
    if (availability.state === "unavailable") {
      return {
        status: "unavailable",
        error: unavailableError(action, availability),
      };
    }
    if (availability.approval.required && availability.approval.state === "rejected") {
      return {
        status: "unavailable",
        error: errorCard(
          action.actionId,
          "APPROVAL_REJECTED",
          availability.message ?? "该操作的审批已被拒绝。",
          availability,
        ),
      };
    }

    const layoutConfirmationRequired =
      action.type === "workbench.open_editor" ||
      availability.layoutEffect === "material";
    if (layoutConfirmationRequired) {
      const preview = await this.#commandBus.preview(request, context);
      this.#pending.set(action.actionId, {
        action: cloneAction(action),
        origin,
        layoutConfirmationRequired: true,
      });
      return {
        status: "awaiting_confirmation",
        action,
        origin,
        preview,
      };
    }

    if (availability.approval.required && availability.approval.state !== "approved") {
      this.#pending.set(action.actionId, {
        action: cloneAction(action),
        origin,
        layoutConfirmationRequired: false,
      });
      return {
        status: "waiting_approval",
        action,
        origin,
        approvalId: availability.approval.approvalId,
      };
    }

    this.#pending.set(action.actionId, {
      action: cloneAction(action),
      origin,
      layoutConfirmationRequired: false,
    });
    return { status: "ready", action, origin };
  }

  async executePrepared(
    actionId: string,
    context: WorkbenchContextSnapshot,
  ): Promise<ActionExecutionResult> {
    const pending = this.#pending.get(actionId);
    if (pending?.layoutConfirmationRequired) {
      return {
        status: "rejected",
        error: errorCard(
          actionId,
          "LAYOUT_CONFIRMATION_REQUIRED",
          "布局变化必须先预览并显式确认。",
        ),
      };
    }

    return this.#execute(actionId, context);
  }

  async confirmLayoutAndExecute(
    actionId: string,
    context: WorkbenchContextSnapshot,
  ): Promise<ActionExecutionResult> {
    const pending = this.#pending.get(actionId);
    if (!pending?.layoutConfirmationRequired) {
      return {
        status: "rejected",
        error: errorCard(
          actionId,
          "LAYOUT_ACTION_NOT_PREPARED",
          "没有可确认的布局预览。",
        ),
      };
    }

    return this.#execute(actionId, context);
  }

  cancel(actionId: string): boolean {
    return this.#pending.delete(actionId);
  }

  async #execute(
    actionId: string,
    context: WorkbenchContextSnapshot,
  ): Promise<ActionExecutionResult> {
    const pending = this.#pending.get(actionId);
    if (!pending) {
      return {
        status: "rejected",
        error: errorCard(
          actionId,
          "ACTION_NOT_PREPARED",
          "操作尚未准备或已经取消。",
        ),
      };
    }

    const request = toCommandRequest(pending.action, pending.origin);
    const availability = await this.#commandBus.inspect(request, context);
    if (availability.state === "unavailable") {
      this.#pending.delete(actionId);
      return {
        status: "rejected",
        error: unavailableError(pending.action, availability),
      };
    }

    if (availability.approval.required && availability.approval.state === "rejected") {
      this.#pending.delete(actionId);
      return {
        status: "rejected",
        error: errorCard(
          actionId,
          "APPROVAL_REJECTED",
          availability.message ?? "该操作的审批已被拒绝。",
          availability,
        ),
      };
    }

    if (availability.approval.required && availability.approval.state !== "approved") {
      return {
        status: "waiting_approval",
        approvalId: availability.approval.approvalId,
      };
    }

    const result = await this.#commandBus.execute(request, context);
    this.#pending.delete(actionId);
    return { status: "executed", result };
  }
}
