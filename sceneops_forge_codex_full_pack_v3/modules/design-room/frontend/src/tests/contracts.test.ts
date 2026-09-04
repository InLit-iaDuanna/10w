import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

import {
  findMyWayHomeBible,
  findMyWayHomeGdd,
  keyDoorFeatureSpec,
  warehouseEscapeFeatureSpec,
} from "../fixtures/designDocuments.ts";

const schemaFiles = [
  "events/design.project_bible.versioned.v1.schema.json",
  "events/design.feature_spec.versioned.v1.schema.json",
  "events/design.feature_spec.marked_ready.v1.schema.json",
  "events/design.decision.recorded.v1.schema.json",
  "manifests/project-bible.v1.schema.json",
  "manifests/gdd.v1.schema.json",
  "manifests/feature-spec.v1.schema.json",
  "manifests/design-change-set.v1.schema.json",
] as const;

async function readContract(relativePath: string) {
  const url = new URL(`../../../contracts/${relativePath}`, import.meta.url);
  return JSON.parse(await readFile(url, "utf8"));
}

test("all Design Room JSON Schemas have unique versioned contract IDs", async () => {
  const schemas = await Promise.all(schemaFiles.map(readContract));
  assert.equal(new Set(schemas.map((schema) => schema.$id)).size, schemas.length);
  for (const schema of schemas) {
    assert.equal(schema.$schema, "https://json-schema.org/draft/2020-12/schema");
    assert.equal(schema.type, "object");
    assert.ok(schema.$id.endsWith("/v1"));
    assert.ok(schema.required.length > 0);
  }
});

test("Find My Way Home and Warehouse Escape JSON examples match deterministic fixtures", async () => {
  const [bible, gdd, feature, warehouse] = await Promise.all([
    readContract("examples/find-my-way-home.project-bible.json"),
    readContract("examples/find-my-way-home.gdd.json"),
    readContract("examples/find-my-way-home.feature-spec.json"),
    readContract("examples/warehouse-escape.feature-spec.json"),
  ]);
  assert.deepEqual(bible, findMyWayHomeBible);
  assert.deepEqual(gdd, findMyWayHomeGdd);
  assert.deepEqual(feature, keyDoorFeatureSpec);
  assert.deepEqual(warehouse, warehouseEscapeFeatureSpec);
});
