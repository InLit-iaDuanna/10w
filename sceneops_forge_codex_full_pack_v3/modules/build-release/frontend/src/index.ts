import { commandDefinitions } from "./commands/definitions.ts";
import { editorDefinitions } from "./editors/definitions.ts";
import { manifest } from "./manifest.ts";

export const moduleContribution = {
  manifest,
  editors: editorDefinitions,
  commands: commandDefinitions,
} as const;
