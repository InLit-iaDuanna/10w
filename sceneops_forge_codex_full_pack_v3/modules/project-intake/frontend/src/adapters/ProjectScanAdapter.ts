import type {
  ExecutionMode,
  IntakeFieldKey,
  ProjectIntakeValues,
  ProjectRoot,
} from "../contracts.ts";

export type CompletedProjectScanMode = Exclude<ExecutionMode, "planned" | "blocked">;

export interface ProjectScanHealth {
  readonly status: "online" | "offline" | "permission-denied";
  readonly checkedAt: string;
  readonly message: string;
}

export interface ProjectScanRequest {
  readonly projectId: string;
  readonly projectRoot: ProjectRoot;
}

export interface ProjectScanCapabilities {
  readonly adapterVersion: string;
  readonly detectableFields: readonly IntakeFieldKey[];
  readonly supportsCancellation: boolean;
}

export interface ProjectScanReport {
  readonly adapterId: string;
  readonly adapterVersion: string;
  readonly scanId: string;
  readonly scannedAt: string;
  readonly mode: CompletedProjectScanMode;
  readonly detected: Partial<ProjectIntakeValues>;
  readonly warnings: readonly string[];
}

export interface ProjectScanAdapter {
  readonly adapterId: string;
  healthCheck(): Promise<ProjectScanHealth>;
  capabilities(): Promise<ProjectScanCapabilities>;
  scan(request: ProjectScanRequest, signal?: AbortSignal): Promise<ProjectScanReport>;
}

export class DeterministicProjectScanAdapter implements ProjectScanAdapter {
  readonly adapterId: string;
  readonly #health: ProjectScanHealth;
  readonly #report: ProjectScanReport;

  constructor(health: ProjectScanHealth, report: ProjectScanReport) {
    this.adapterId = report.adapterId;
    this.#health = health;
    this.#report = report;
  }

  async healthCheck(): Promise<ProjectScanHealth> {
    return this.#health;
  }

  async capabilities(): Promise<ProjectScanCapabilities> {
    return {
      adapterVersion: this.#report.adapterVersion,
      detectableFields: Object.keys(this.#report.detected).sort() as IntakeFieldKey[],
      supportsCancellation: true,
    };
  }

  async scan(request: ProjectScanRequest, signal?: AbortSignal): Promise<ProjectScanReport> {
    if (signal?.aborted === true) throw new DOMException("Project scan cancelled", "AbortError");
    if (request.projectRoot.absolutePath.trim().length === 0) {
      throw new Error("The fixture adapter received an empty root.");
    }
    return this.#report;
  }
}
