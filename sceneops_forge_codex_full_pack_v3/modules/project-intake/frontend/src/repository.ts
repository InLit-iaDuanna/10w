import type { ProjectIntakeRecord } from "./contracts.ts";

export interface ProjectIntakeRepository {
  get(intakeId: string): ProjectIntakeRecord | null;
  save(record: ProjectIntakeRecord): void;
}

export class InMemoryProjectIntakeRepository implements ProjectIntakeRepository {
  readonly #records = new Map<string, ProjectIntakeRecord>();

  get(intakeId: string): ProjectIntakeRecord | null {
    return this.#records.get(intakeId) ?? null;
  }

  save(record: ProjectIntakeRecord): void {
    this.#records.set(record.intakeId, record);
  }
}
