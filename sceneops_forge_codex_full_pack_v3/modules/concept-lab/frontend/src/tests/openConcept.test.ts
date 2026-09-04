import assert from "node:assert/strict";
import test from "node:test";

import { openConcept } from "../index.ts";

test("chat and task links use the same typed open-editor handler", () => {
  const common = {
    conceptId: "cpt_key",
    projectId: "prj_remember_home",
    taskId: "tsk_key_concept",
  };
  const fromChat = openConcept({ ...common, source: "chat" });
  const fromTask = openConcept({ ...common, source: "task_link" });
  assert.deepEqual(fromChat, fromTask);
  assert.equal(fromChat.type, "workbench.open_editor");
  assert.equal(fromChat.requireConfirmation, true);
  assert.equal(fromChat.context.activeTaskId, "tsk_key_concept");
});
