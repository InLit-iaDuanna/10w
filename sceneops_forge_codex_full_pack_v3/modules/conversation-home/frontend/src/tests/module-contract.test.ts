import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";
import { moduleContribution } from "../index.ts";
import { validateAssistantAction } from "../assistant-actions/validate.ts";

const moduleRoot = new URL("../../../", import.meta.url);

test("module manifest declares the required identity, dependencies, flag, and public entry", () => {
  const yaml = readFileSync(new URL("module.yaml", moduleRoot), "utf8");
  assert.match(yaml, /^schema_version: 1$/m);
  assert.match(yaml, /^id: conversation-home$/m);
  assert.match(yaml, /^feature_flag: conversation_home$/m);
  assert.match(yaml, /^    - core-kernel$/m);
  assert.match(yaml, /^    - module-runtime$/m);
  assert.match(yaml, /^    - assistant\.conversation$/m);
  assert.match(yaml, /^  frontend: \.\/frontend\/src\/index\.ts$/m);
  assert.equal(existsSync(new URL("frontend/src/index.ts", moduleRoot)), true);
  assert.equal(existsSync(new URL("README.md", moduleRoot)), true);
  assert.equal(existsSync(new URL("AGENTS.md", moduleRoot)), true);
});

test("public contribution registers one lazy conversation editor", () => {
  assert.equal(moduleContribution.manifest.id, "conversation-home");
  assert.equal(moduleContribution.editors.length, 1);
  const editor = moduleContribution.editors[0];
  assert.equal(editor?.id, "assistant.conversation");
  assert.equal(editor?.singleton, true);
  assert.equal(editor?.defaultPlacement, "center");
  assert.equal(typeof editor?.load, "function");
  assert.deepEqual(editor?.optionalIntegrations, ["llm-provider"]);
});

test("versioned JSON contracts and deterministic example are readable", () => {
  const actionSchema = JSON.parse(
    readFileSync(new URL("contracts/assistant-action.schema.json", moduleRoot), "utf8"),
  );
  const recordSchema = JSON.parse(
    readFileSync(new URL("contracts/conversation-record.schema.json", moduleRoot), "utf8"),
  );
  const actionExample = JSON.parse(
    readFileSync(
      new URL(
        "contracts/examples/open-scene-view-right.action.json",
        moduleRoot,
      ),
      "utf8",
    ),
  );
  assert.equal(actionSchema.$schema, "https://json-schema.org/draft/2020-12/schema");
  assert.equal(recordSchema.properties.schemaVersion.const, 1);
  assert.equal(validateAssistantAction(actionExample).ok, true);
});
