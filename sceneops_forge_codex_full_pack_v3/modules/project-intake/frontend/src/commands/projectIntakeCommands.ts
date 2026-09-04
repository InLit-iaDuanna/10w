import type {
  CommandAvailability,
  CommandMetadata,
  ConversationProjectIntent,
  ExistingProjectScanInput,
  IntakeDraftedPayload,
  IntakeEventEnvelope,
  IntakeFieldConfirmedPayload,
  IntakeFieldKey,
  NewProjectIntakeInput,
  ProjectIntakeCommandContext,
  ProjectIntakeRecord,
  ProjectIntakeValues,
  WorkbenchOpenEditorAction,
} from "../contracts.ts";
import { ProjectIntakeError } from "../contracts.ts";
import type { ProjectScanAdapter } from "../adapters/ProjectScanAdapter.ts";
import { ProjectIntakeService } from "../service.ts";
import { listFieldsByConfidence } from "../validation.ts";

export interface IntakeDraftCommandResult {
  readonly record: ProjectIntakeRecord;
  readonly event: IntakeEventEnvelope<IntakeDraftedPayload>;
  readonly openEditorAction: WorkbenchOpenEditorAction;
}

export interface ConfirmIntakeFieldInput<K extends IntakeFieldKey = IntakeFieldKey> {
  readonly intakeId: string;
  readonly field: K;
  readonly value: ProjectIntakeValues[K];
}

export interface ConfirmIntakeFieldResult {
  readonly record: ProjectIntakeRecord;
  readonly event: IntakeEventEnvelope<IntakeFieldConfirmedPayload>;
}

export function commandAvailability(
  context: ProjectIntakeCommandContext,
  requiredPermissions: readonly string[],
): CommandAvailability {
  if (!context.moduleEnabled) {
    return { available: false, code: "MODULE_DISABLED", message: "Project Intake 模块已关闭。" };
  }
  const missing = requiredPermissions.find((permission) => !context.permissions.has(permission));
  if (missing !== undefined) {
    return { available: false, code: "PERMISSION_DENIED", message: `缺少权限：${missing}` };
  }
  return { available: true, code: "AVAILABLE", message: "可执行" };
}

function assertCommandAvailable(
  context: ProjectIntakeCommandContext,
  requiredPermissions: readonly string[],
): void {
  const availability = commandAvailability(context, requiredPermissions);
  if (availability.available) return;
  const code = availability.code === "MODULE_DISABLED" ? "MODULE_DISABLED" : "PERMISSION_DENIED";
  throw new ProjectIntakeError(
    code,
    availability.message,
    false,
    code === "MODULE_DISABLED" ? ["module.enable"] : ["permissions.request"],
  );
}

function openEditor(record: ProjectIntakeRecord): WorkbenchOpenEditorAction {
  return {
    type: "workbench.open_editor",
    editorId: "project.intake",
    placement: { mode: "tab" },
    context: { projectId: record.projectId },
    requireConfirmation: false,
  };
}

function draftedEvent(
  record: ProjectIntakeRecord,
  metadata: CommandMetadata,
  actorType: "user" | "assistant",
): IntakeEventEnvelope<IntakeDraftedPayload> {
  return {
    eventId: metadata.eventId,
    eventType: "project.intake.drafted",
    eventVersion: 1,
    occurredAt: metadata.occurredAt,
    projectId: record.projectId,
    correlationId: metadata.correlationId,
    causationId: metadata.commandId,
    actor: { type: actorType, id: metadata.actorId },
    mode: record.mode,
    payload: {
      intakeId: record.intakeId,
      kind: record.kind,
      status: record.status,
      inferredFields: listFieldsByConfidence(record, "inferred"),
      missingFields: listFieldsByConfidence(record, "missing"),
    },
  };
}

export function createProjectIntakeCommandHandlers(
  service: ProjectIntakeService,
  adapters: ReadonlyMap<string, ProjectScanAdapter>,
) {
  return {
    createNew(
      context: ProjectIntakeCommandContext,
      input: NewProjectIntakeInput,
      metadata: CommandMetadata,
    ): IntakeDraftCommandResult {
      assertCommandAvailable(context, ["project:write"]);
      const record = service.createNew(input);
      return { record, event: draftedEvent(record, metadata, "user"), openEditorAction: openEditor(record) };
    },

    createFromConversation(
      context: ProjectIntakeCommandContext,
      input: ConversationProjectIntent,
      metadata: CommandMetadata,
    ): IntakeDraftCommandResult {
      assertCommandAvailable(context, ["project:write"]);
      const record = service.createFromConversation(input);
      return {
        record,
        event: draftedEvent(record, metadata, "assistant"),
        openEditorAction: openEditor(record),
      };
    },

    async scanExisting(
      context: ProjectIntakeCommandContext,
      input: ExistingProjectScanInput,
      metadata: CommandMetadata,
      signal?: AbortSignal,
    ): Promise<IntakeDraftCommandResult> {
      assertCommandAvailable(context, ["project:write", "project:scan"]);
      const adapter = adapters.get(input.adapterId);
      if (adapter === undefined) {
        throw new ProjectIntakeError(
          "ADAPTER_NOT_FOUND",
          `未注册扫描器：${input.adapterId}`,
          false,
          ["integration.open"],
        );
      }
      const record = await service.scanExisting(input, adapter, signal);
      return { record, event: draftedEvent(record, metadata, "user"), openEditorAction: openEditor(record) };
    },

    confirmField<K extends IntakeFieldKey>(
      context: ProjectIntakeCommandContext,
      input: ConfirmIntakeFieldInput<K>,
      metadata: CommandMetadata,
    ): ConfirmIntakeFieldResult {
      assertCommandAvailable(context, ["project:write"]);
      const record = service.confirm(
        input.intakeId,
        input.field,
        input.value,
        metadata.actorId,
        metadata.occurredAt,
      );
      return {
        record,
        event: {
          eventId: metadata.eventId,
          eventType: "project.intake.field_confirmed",
          eventVersion: 1,
          occurredAt: metadata.occurredAt,
          projectId: record.projectId,
          correlationId: metadata.correlationId,
          causationId: metadata.commandId,
          actor: { type: "user", id: metadata.actorId },
          mode: record.mode,
          payload: { intakeId: record.intakeId, field: input.field, status: record.status },
        },
      };
    },
  };
}

export type ProjectIntakeCommandHandlers = ReturnType<typeof createProjectIntakeCommandHandlers>;
