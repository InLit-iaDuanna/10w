import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const contractFiles = [
  "events/project.intake.drafted.v1.schema.json",
  "events/project.intake.field_confirmed.v1.schema.json",
  "manifests/project-intake-record.v1.schema.json",
  "manifests/project-scan-report.v1.schema.json",
] as const;

async function readContract(relativePath: string) {
  const url = new URL(`../../../contracts/${relativePath}`, import.meta.url);
  return JSON.parse(await readFile(url, "utf8"));
}

test("all Project Intake JSON Schemas are versioned objects with unique IDs", async () => {
  const schemas = await Promise.all(contractFiles.map(readContract));
  assert.equal(new Set(schemas.map((schema) => schema.$id)).size, schemas.length);
  for (const schema of schemas) {
    assert.equal(schema.$schema, "https://json-schema.org/draft/2020-12/schema");
    assert.equal(schema.type, "object");
    assert.ok(schema.$id.endsWith("/v1"));
    assert.ok(schema.required.length > 0);
  }
});

test("deterministic examples expose execution mode and critical confidence", async () => {
  const intake = await readContract("examples/find-my-way-home.project-intake.json");
  const scan = await readContract("examples/warehouse-escape.project-scan.json");
  assert.equal(intake.mode, "mock");
  assert.equal(intake.fields.targetPlatforms.confidence, "confirmed");
  assert.equal(intake.fields.projectRoots.confidence, "confirmed");
  assert.equal(scan.mode, "mock");
  assert.equal(scan.adapterVersion, "0.1.0-fixture");
  assert.equal(scan.detected.teamRoles, undefined);
});
