import type {
  ConversationProjectIntent,
  ExistingProjectScanInput,
  IntakeFieldKey,
  NewProjectIntakeInput,
  ProjectIntakeRecord,
  ProjectIntakeValues,
} from "./contracts.ts";
import { ProjectIntakeError } from "./contracts.ts";
import type { ProjectScanAdapter } from "./adapters/ProjectScanAdapter.ts";
import {
  confirmIntakeField,
  createConversationProjectIntake,
  createExistingProjectIntake,
  createNewProjectIntake,
} from "./intake.ts";
import type { ProjectIntakeRepository } from "./repository.ts";
import { validateProjectRoot } from "./validation.ts";

export class ProjectIntakeService {
  readonly #repository: ProjectIntakeRepository;

  constructor(repository: ProjectIntakeRepository) {
    this.#repository = repository;
  }

  createNew(input: NewProjectIntakeInput): ProjectIntakeRecord {
    const record = createNewProjectIntake(input);
    this.#repository.save(record);
    return record;
  }

  createFromConversation(input: ConversationProjectIntent): ProjectIntakeRecord {
    const record = createConversationProjectIntake(input);
    this.#repository.save(record);
    return record;
  }

  async scanExisting(
    input: ExistingProjectScanInput,
    adapter: ProjectScanAdapter,
    signal?: AbortSignal,
  ): Promise<ProjectIntakeRecord> {
    assertProjectRoot(input);
    try {
      const health = await adapter.healthCheck();
      assertIntegrationAvailable(health.status, adapter.adapterId);
      const report = await adapter.scan(
        { projectId: input.projectId, projectRoot: input.projectRoot! },
        signal,
      );
      if (report.adapterId !== adapter.adapterId) {
        throw new Error(`Scan report adapter mismatch: ${report.adapterId}`);
      }
      const record = createExistingProjectIntake(input, report);
      this.#repository.save(record);
      return record;
    } catch (error) {
      if (error instanceof ProjectIntakeError) throw error;
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ProjectIntakeError("SCAN_CANCELLED", "项目扫描已取消。", false, []);
      }
      throw new ProjectIntakeError(
        "SCAN_FAILED",
        error instanceof Error ? error.message : "项目扫描失败。",
        true,
        ["integration.retry", "integration.open"],
      );
    }
  }

  confirm<K extends IntakeFieldKey>(
    intakeId: string,
    key: K,
    value: ProjectIntakeValues[K],
    actorId: string,
    occurredAt: string,
  ): ProjectIntakeRecord {
    const existing = this.#repository.get(intakeId);
    if (existing === null) {
      throw new ProjectIntakeError("INTAKE_NOT_FOUND", "找不到项目入口草稿。", false, []);
    }
    const confirmed = confirmIntakeField(existing, key, value, actorId, occurredAt);
    this.#repository.save(confirmed);
    return confirmed;
  }

  get(intakeId: string): ProjectIntakeRecord | null {
    return this.#repository.get(intakeId);
  }
}

function assertProjectRoot(
  input: ExistingProjectScanInput,
): asserts input is ExistingProjectScanInput & { readonly projectRoot: NonNullable<ExistingProjectScanInput["projectRoot"]> } {
  const issue = validateProjectRoot(input.projectRoot);
  if (issue === null) return;
  const code = issue.code === "INVALID_PROJECT_ROOT" ? "INVALID_PROJECT_ROOT" : "MISSING_PROJECT_ROOT";
  throw new ProjectIntakeError(code, issue.message, false, ["project.root.select"]);
}

function assertIntegrationAvailable(
  status: "online" | "offline" | "permission-denied",
  adapterId: string,
): void {
  if (status === "online") return;
  const denied = status === "permission-denied";
  throw new ProjectIntakeError(
    denied ? "INTEGRATION_PERMISSION_DENIED" : "INTEGRATION_OFFLINE",
    denied ? `${adapterId} 无权扫描该目录。` : `${adapterId} 当前未连接。`,
    !denied,
    denied ? ["integration.permissions.open"] : ["integration.open", "run.retry"],
  );
}
