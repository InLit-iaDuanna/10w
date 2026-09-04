import type { ProjectScanAdapter } from "./adapters/ProjectScanAdapter.ts";
import { createProjectIntakeCommandHandlers } from "./commands/projectIntakeCommands.ts";
import { InMemoryProjectIntakeRepository } from "./repository.ts";
import { ProjectIntakeService } from "./service.ts";

export function createProjectIntakeRuntime(
  adapters: ReadonlyMap<string, ProjectScanAdapter> = new Map(),
) {
  const repository = new InMemoryProjectIntakeRepository();
  const service = new ProjectIntakeService(repository);
  return {
    commands: createProjectIntakeCommandHandlers(service, adapters),
    getIntake: (intakeId: string) => service.get(intakeId),
  } as const;
}
