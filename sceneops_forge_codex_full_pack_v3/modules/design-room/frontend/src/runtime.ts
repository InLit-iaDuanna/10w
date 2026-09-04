import { createDesignRoomCommandHandlers } from "./commands/designRoomCommands.ts";
import { InMemoryDesignDocumentRepository } from "./repository.ts";
import { DesignRoomService } from "./service.ts";

export function createDesignRoomRuntime() {
  const repository = new InMemoryDesignDocumentRepository();
  const service = new DesignRoomService(repository);
  return {
    commands: createDesignRoomCommandHandlers(service),
    latestFeature: (featureSpecId: string) => service.latestFeature(featureSpecId),
    getChangeSet: (changeSetId: string) => service.getChangeSet(changeSetId),
    diff: service.diff.bind(service),
  } as const;
}
