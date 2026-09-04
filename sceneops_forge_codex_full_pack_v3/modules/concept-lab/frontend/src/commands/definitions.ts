import { openConcept } from "./openConcept.ts";

const commandIds = [
  "concept.open",
  "concept.style_bible.open",
  "concept.create",
  "concept.change.propose",
  "concept.change.approve",
  "concept.change.apply",
  "concept.reference.import",
  "concept.variant.import",
  "concept.variant.generate",
  "concept.variant.compare",
  "concept.variant.comment",
  "concept.variant.review",
  "concept.style.check",
  "concept.asset_spec_draft.compile",
] as const;

export const conceptCommands = commandIds.map((id) => ({
  id,
  title: id === "concept.open" ? "打开概念板" : id,
  inputContract: `openapi://concept-lab/${id}`,
  requiredPermissions: permissionsFor(id),
  requiredIntegrations: [],
  optionalIntegrations: id === "concept.variant.generate" ? ["image-generation"] : [],
}));

export const conceptOpenCommand = {
  ...conceptCommands[0],
  execute: openConcept,
};

function permissionsFor(id: (typeof commandIds)[number]): string[] {
  if (["concept.open", "concept.style_bible.open", "concept.variant.compare"].includes(id)) {
    return ["concept:read"];
  }
  if (["concept.change.approve", "concept.variant.review", "concept.style.check"].includes(id)) {
    return ["concept:review"];
  }
  if (id === "concept.asset_spec_draft.compile") {
    return ["concept:read", "asset-spec:draft"];
  }
  return ["concept:write"];
}
